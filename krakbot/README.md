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

## Web UI redesign (implemented)

The frontend now ships with an operator-focused redesign:

- App shell with responsive left nav (mobile collapses to horizontal strip)
- Overview KPI dashboard
- Strategy comparison matrix
- Strategy detail deep-dive page
- Trades + decision trace inspector
- Market detail panel and polished market registry table
- Controls with safety arming + typed confirmation for dangerous actions
- Benchmark & wallet intelligence panel
- Reusable tokens/components (`tokens.css`, `AppShell`, `PageHeader`, `StatCard`, `Badge`)

See implementation tracker: `docs/ui-redesign-implementation-plan.md`.

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
See `docs/eif-phase3.md` for operator UI workflows (why skipped? what changed?) and rollback/kill-switch runbook.

## Wallet Intelligence Benchmark (WIB) scaffold

Design/handoff spec:
- `docs/wallet-intelligence-benchmark-handoff.md`

MVP scaffold endpoints:

```bash
curl -s http://localhost:8010/api/wallet-intel/health
curl -s -X POST http://localhost:8010/api/wallet-intel/admin/run-pipeline \
  -H 'content-type: application/json' \
  -d '{"provider":"helius"}'
curl -s http://localhost:8010/api/wallet-intel/cohorts/top_sol_active_wallets/latest
curl -s http://localhost:8010/api/wallet-intel/wallets/w_solana_wallet_demo_1/explainability
curl -s -X POST http://localhost:8010/api/wallet-intel/alignment/tag \
  -H 'content-type: application/json' \
  -d '{"strategy_instance_id":"inst_demo","strategy_side":"buy","scope":"trade"}'
curl -s http://localhost:8010/api/wallet-intel/alignment/summary?lookback_days=7
```

Phase-2 provider config (real Helius fetch, fallback to stub when unset):

```bash
WALLET_INTEL_HELIUS_API_KEY=your_key
WALLET_INTEL_SOLANA_WATCHLIST=wallet1,wallet2,wallet3
WALLET_INTEL_DEFAULT_PRICE_REF_USD=85
WALLET_INTEL_MIN_T1_EVENTS_30D=20
WALLET_INTEL_MIN_ACTIVE_DAYS_30D=10
WALLET_INTEL_MIN_NOTIONAL_30D=25000
WALLET_INTEL_MIN_SOL_RELEVANCE=0.8
WALLET_INTEL_RECENCY_DAYS=5
WALLET_INTEL_COHORT_TARGET_SIZE=50
WALLET_INTEL_COHORT_HYSTERESIS_BUFFER=15
WALLET_INTEL_ALIGNMENT_MIN_CONFIDENCE=35
LIVE_PAPER_TEST_MAX_ACTIVE_STRATEGIES=3
```

## Jason Agent (GPT model in Model Arena)

Jason is now wired as an Arena agent (`agent_id: jason`) with virtual Hyperliquid-style perp paper trading rules:

- Starting balance: `$1000`
- Symbols: `BTC`, `ETH`, `SOL`
- Actions: `long`, `short`, `close`, `hold`
- Max leverage: `20x`
- Max allocation: `50%` of remaining balance per trade
- Decision packets are recorded for Model Arena ranking/compare visibility

Backend env:

```bash
OPENAI_API_KEY=...your key...
JASON_AGENT_MODEL=gpt-5.4
```

Run + inspect:

```bash
curl -s -X POST http://localhost:8010/api/agents/jason/run-once
curl -s http://localhost:8010/api/agents/jason/state
curl -s 'http://localhost:8010/api/agents/jason/trades?limit=50'
curl -s 'http://localhost:8010/api/agents/decision-packets?agent_id=jason&limit=50'
```

## Tailscale WebUI Access

Current node Tailscale IP can access frontend directly (tailnet-only):

```bash
http://100.106.146.9:5173
```

Verification command used:

```bash
curl -I http://100.106.146.9:5173
# expected: HTTP/1.1 200 OK
```

If you want a nicer Tailscale Serve URL instead of `:5173`, run once with sudo on host:

```bash
sudo tailscale set --operator=$USER
sudo tailscale serve --bg --http 18790 127.0.0.1:5173
tailscale serve status
```

Then open the shown tailnet URL on port `18790`.

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
