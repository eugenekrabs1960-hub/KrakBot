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
