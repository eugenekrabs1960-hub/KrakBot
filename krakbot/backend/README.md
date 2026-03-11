# Krakbot Backend

FastAPI control plane scaffold + Phase 1/2/3/4/5 foundations.

## Run locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Ensure postgres/redis are running (see ../deploy/docker-compose.yml)
python -m app.db.migrate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

## Implemented in Phase 1
- Kraken v2 websocket ingestion for SOL/USD trades + orderbook snapshots
- 1m candle aggregation from trade stream
- Canonical persistence tables: `market_trades`, `orderbook_snapshots`, `candles`
- Live websocket fanout endpoint: `ws://localhost:8010/api/ws`

## Implemented in Phase 2
- Strategy registry + strategy instance APIs
- Isolated `paper_portfolios` (1 per strategy instance)
- Durable bot state machine via `system_state`
- Canonical execution normalization tables: `orders`, `executions`
- Paper order submission through Freqtrade adapter boundary

## Implemented in Phase 3
- Position and portfolio balance tracking per strategy instance
- Performance snapshot updates after each fill
- Optional Freqtrade REST bridge with safe paper fallback
- Strategy detail and richer comparison fields (position/equity)

## Implemented in Phase 4
- Idempotent paper order submission with request replay safety
- Reconciliation service + reconciliation history APIs
- Worker checkpoint persistence for restart diagnostics
- Reliability-oriented DB primitives for ongoing hardening

## Implemented in Phase 5
- Config-driven market registry (`market_registry`) for multi-coin activation
- Strategy-to-market assignment table (`strategy_markets`)
- Market registry APIs and enable/disable flow
- Kraken ingestion subscription now driven by enabled market registry rows

## Tests

```bash
# from repo root
PYTHONPATH=backend ./backend/.venv/bin/python -m pytest -q \
  backend/tests/test_paper_fill_pricing.py \
  backend/tests/test_model_lab.py \
  backend/tests/test_model_lab_api.py
```

## API endpoints
- `GET /api/health`
- `GET /api/market/snapshot`
- `GET /api/market/trades?limit=100`
- `GET /api/market/orderbook`
- `GET /api/market/candles?limit=200`
- `GET /api/control/bot`
- `POST /api/control/bot`
- `POST /api/control/strategy/toggle`
- `POST /api/strategies/instances`
- `GET /api/strategies`
- `GET /api/strategies/{strategy_instance_id}`
- `GET /api/trades`
- `POST /api/trades/paper-order` (requires `x-idempotency-key`)
- `POST /api/reliability/reconcile/all`
- `POST /api/reliability/reconcile/{strategy_instance_id}`
- `GET /api/reliability/reconciliations`
- `GET /api/markets`
- `POST /api/markets`
- `POST /api/markets/{market_id}/toggle`
- `POST /api/markets/assign`
