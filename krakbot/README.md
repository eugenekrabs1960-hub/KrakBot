# Krakbot

Multi-coin-ready crypto paper trading platform.

MVP target:
- Venue: Kraken spot
- Pair: SOL/USD
- Engine: Freqtrade (hidden behind adapter)
- UI: React + TypeScript
- Backend: Python (FastAPI)

See architecture: `../kraken_bots/KRAKBOT_MVP_ARCHITECTURE.md`

## Repo layout

- `backend/` FastAPI control plane + orchestration and domain APIs
- `frontend/` React dashboard and controls UI
- `deploy/` local docker compose and env templates

## Current status

This is an architecture-aligned scaffold (contracts + module boundaries), ready for phased implementation.

## Paper Fill Pricing Policy (Strict)

Paper-order fills use **only** the latest `market_trades.price` for the requested market.

- No random fallback pricing
- No orderbook fallback pricing
- No bridge-returned price fallback for paper fill
- If no market trade price is available, order is rejected:
  - `{"accepted":false,"error_code":"no_market_trade_price","message":"No market trade price available for fill","market":"<market>"}`
- Rejected fills do not create executions and do not mutate position/portfolio.
- Idempotent replay returns the same stored response for both success and failure.

## Live Paper Test Mode (continuous strategy-driven paper actions)

Use this mode when you want visible ongoing SOL/USD paper activity in UI/API without any real-money trading.

### 1) Enable mode (off by default)

Set backend env (for docker compose, put in `deploy/.env`):

```bash
LIVE_PAPER_TEST_MODE_ENABLED=true
LIVE_PAPER_TEST_MARKET=SOL/USD
LIVE_PAPER_TEST_LOOP_INTERVAL_SEC=5
LIVE_PAPER_TEST_ORDER_QTY=0.05
LIVE_PAPER_TEST_MAX_ORDERS_PER_MINUTE=6
LIVE_PAPER_TEST_MIN_SECONDS_BETWEEN_ORDERS=5
LIVE_PAPER_TEST_FORCE_PAPER_ONLY=true
```

Safe defaults are already off (`LIVE_PAPER_TEST_MODE_ENABLED=false`).

### 2) Start stack

```bash
cd deploy
docker compose up -d --build
```

### 3) Start bot runtime and create at least one enabled SOL/USD strategy

```bash
# Start orchestration state machine
curl -s -X POST http://localhost:8010/api/control/bot \
  -H 'content-type: application/json' \
  -d '{"command":"start"}'

# Create strategy instance (enabled by default)
curl -s -X POST http://localhost:8010/api/strategies/instances \
  -H 'content-type: application/json' \
  -d '{"strategy_name":"trend_following","market":"SOL/USD","instrument_type":"spot","starting_equity_usd":10000,"params":{"live_paper_test":true}}'
```

### 4) Observe activity (API + UI)

Watch config/toggle state:

```bash
curl -s http://localhost:8010/api/control/live-paper-test-mode
```

Watch trade flow:

```bash
watch -n 2 "curl -s 'http://localhost:8010/api/trades?limit=20'"
watch -n 2 "curl -s 'http://localhost:8010/api/strategies'"
watch -n 2 "curl -s 'http://localhost:8010/api/market/trades?limit=5'"
```

UI panels to watch (`http://localhost:5173`):
- **Trade History** (new fills)
- **Strategy Comparison** (trade_count / position / equity updates)
- **Controls** (bot state must be `running`)

### 5) Control constraints respected

- `pause` / `stop` prevents new auto order attempts.
- `resume` / `start` allows attempts again.
- Strategy-level toggle (`/api/control/strategy/toggle`) is respected.
- Rate guards: max orders/minute + min seconds between orders.
- Decision/order attempt events are logged as `paper_test.decision` and `paper_test.order_attempt`.

## EIF Phases 1-2 (Capture + Optional Filter Enforcement + Analytics)

Enable explicitly (defaults are safe/off):

```bash
EIF_CAPTURE_ENABLED=true
EIF_SCORECARD_COMPUTE_ENABLED=true
EIF_FILTER_SHADOW_MODE=true        # evaluate + trace only
EIF_FILTER_ENFORCE_MODE=false      # keep false unless you want blocking
EIF_FILTER_FAIL_CLOSED=false       # fail-open default
EIF_ANALYTICS_API_ENABLED=true
```

Operator endpoints:

```bash
curl -s http://localhost:8010/api/control/eif-flags
curl -s http://localhost:8010/api/eif/summary
curl -s 'http://localhost:8010/api/eif/filter-decisions?limit=20'
curl -s 'http://localhost:8010/api/eif/regimes?limit=20'
curl -s 'http://localhost:8010/api/eif/scorecards?limit=20'
curl -s 'http://localhost:8010/api/eif/trade-trace?limit=20'
```

See `docs/eif-phase1.md` and `docs/eif-phase2.md` for vocabularies, precedence policy, and filter trace schema.

## Known Working Verification

Start stack:

```bash
cd deploy
docker compose up -d
```

One-command smoke test:

```bash
cd ..
./scripts/smoke_local_stack.sh
```

Expected final line:

```text
✅ KrakBot smoke test passed
```

Manual API verification (exact curl commands):

```bash
# 1) health
curl -s http://localhost:8010/api/health
# expected: {"ok":true,...}

# 2) bot state (stopped/running/paused)
curl -s http://localhost:8010/api/control/bot
# expected: {"state":"stopped"} (or running/paused)

# 3) create strategy instance
curl -s -X POST http://localhost:8010/api/strategies/instances \
  -H 'content-type: application/json' \
  -d '{"strategy_name":"trend_following","market":"SOL/USD","instrument_type":"spot","starting_equity_usd":10000,"params":{"verify":true}}'
# expected: {"ok":true,"strategy_instance_id":"inst_...","paper_portfolio_id":"port_..."}

# 4) submit paper order with idempotency
curl -s -X POST http://localhost:8010/api/trades/paper-order \
  -H 'content-type: application/json' \
  -H 'x-idempotency-key: verify-001' \
  -d '{"strategy_instance_id":"inst_REPLACE","market":"SOL/USD","side":"buy","qty":0.1,"order_type":"limit","limit_price":123.45}'
# expected: {"accepted":true,"order_id":"ord_...","execution_id":"exe_...",...}

# 5) replay same request (same idempotency key)
curl -s -X POST http://localhost:8010/api/trades/paper-order \
  -H 'content-type: application/json' \
  -H 'x-idempotency-key: verify-001' \
  -d '{"strategy_instance_id":"inst_REPLACE","market":"SOL/USD","side":"buy","qty":0.1,"order_type":"limit","limit_price":123.45}'
# expected: exactly the same JSON body as step 4

# 6) list strategies/trades
curl -s http://localhost:8010/api/strategies
curl -s 'http://localhost:8010/api/trades?limit=10'
# expected: arrays with strategy metrics and recent fills
```
