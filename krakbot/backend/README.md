# Krakbot Backend

FastAPI control plane scaffold + Phase 1/2 foundations.

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
- `GET /api/trades`
- `POST /api/trades/paper-order`
