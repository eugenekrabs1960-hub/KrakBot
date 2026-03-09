# Krakbot MVP Architecture (Kraken Spot SOL/USD first, multi-coin-ready)

## 1) Proposed Architecture

Opinionated choice: **modular monolith backend + evented internals** for MVP.

- Keep one deployable Python backend for speed/reliability.
- Split by strict modules/interfaces so components can later be extracted into services.
- Treat **Freqtrade as a pluggable execution engine adapter**, not the system core.
- Use **PostgreSQL as source of truth**, Redis for live pub/sub/cache, and WebSocket push for UI.

### Architecture principles

1. **App owns domain model** (orders, portfolios, PnL, events), not Freqtrade.
2. **Engine-agnostic interfaces** from day one (spot now, futures later).
3. **Per-strategy portfolio isolation** (no shared capital in MVP).
4. **Config-driven market enablement** (SOL/USD enabled first, schema supports many).
5. **Safety-first controls** (manual enable/disable/start/stop; no autonomous strategy mutation).

---

## 2) Component / Service Breakdown

## A. API & Control Plane (FastAPI)
Responsibilities:
- REST + WS endpoints for frontend
- Bot controls: start/stop/pause/resume
- Strategy controls: enable/disable, parameter reload (bounded)
- Health/status endpoints
- Authentication (basic token/session for MVP)

## B. Orchestrator Runtime
Responsibilities:
- Start/monitor strategy workers
- Assign each strategy instance to a dedicated paper portfolio
- Supervise execution engine processes and restart policies
- Publish lifecycle events

## C. Execution Engine Interface + Freqtrade Adapter
`ExecutionEngine` interface (internal contract):
- submit_order(intent)
- cancel_order(order_id)
- fetch_open_orders()
- fetch_positions()
- fetch_fills(since)
- health()

Freqtrade adapter responsibilities:
- Translate canonical order intents ↔ Freqtrade structures
- Run in paper mode only (MVP)
- Normalize fills/orders into canonical DB tables
- Expose minimal engine status to orchestrator

## D. Market Data Ingestion
Responsibilities:
- Kraken WS ingest for trades/order book
- Candle builder or normalized OHLCV ingestion
- Gap detection/reconnect/backfill
- Persist market data + publish update events

## E. Portfolio & Performance Engine
Responsibilities:
- Track balances, positions, realized/unrealized PnL per strategy portfolio
- Compute metrics (win rate, drawdown, trade count, Sharpe-lite later)
- Write periodic performance snapshots

## F. Event & Audit Log Module
Responsibilities:
- Structured logs/events (system, strategy, execution)
- Audit trail for controls/actions and state transitions
- Debug visibility for failure investigation

## G. Frontend (React + TS)
Views:
1. Dashboard
2. Strategy comparison
3. Trade history
4. Market data
5. Controls panel

---

## 3) Data Flow Overview

1. **Ingestion** receives Kraken SOL/USD stream → normalizes → stores to DB.
2. **Strategy worker** consumes latest market state + its own portfolio state.
3. Worker emits canonical **OrderIntent** (buy/sell, size, constraints).
4. **Freqtrade adapter** executes in paper mode, returns order/fill updates.
5. Updates are normalized into canonical tables: orders, fills, positions.
6. **Portfolio engine** recalculates PnL/equity/metrics per strategy.
7. API pushes updates to UI via WebSocket + serves historical data via REST.

---

## 4) Recommended Stack Details

- **Backend:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic
- **Worker model:** asyncio workers (MVP); move to Celery/RQ only if needed
- **DB:** PostgreSQL 15+ (Timescale extension optional for scale)
- **Cache / pubsub:** Redis
- **Frontend:** React + TypeScript + Vite + TanStack Query + charting library
- **Infra:** Docker Compose for MVP (api, worker, postgres, redis, frontend, freqtrade)
- **Observability:** structured JSON logs, health checks, metrics endpoint

---

## 5) High-Level Database / Storage Design

Use canonical domain tables (engine-neutral naming):

- `venues` (kraken)
- `assets` (SOL, USD)
- `markets` (SOL/USD, venue, instrument_type)
- `candles`
- `market_trades`
- `orderbook_snapshots` (and optional deltas)

- `strategies` (template metadata)
- `strategy_instances` (running instance, params, status)
- `paper_portfolios` (1:1 with strategy_instances in MVP)
- `portfolio_balances`
- `positions`

- `orders` (canonical)
- `executions` (fills)
- `performance_snapshots`
- `system_events` / `strategy_events` / `audit_events`

Mapping fields for engine bridge:
- `engine` (e.g., freqtrade)
- `engine_order_id`
- `engine_trade_id`

### Important schema choices for future futures support
Include now (nullable in MVP):
- `instrument_type` (spot, perpetual, futures)
- `contract_size`
- `tick_size`
- `lot_size`
- `leverage`
- `margin_mode`

---

## 6) Modeling Multi-Strategy with Separate Paper Portfolios

MVP model:
- One `strategy_instance` = one isolated `paper_portfolio`.
- Each strategy starts with independent virtual USD bankroll.
- No shared inventory/capital across strategies.
- Position and PnL calculations scoped by `strategy_instance_id`.

This guarantees fair strategy comparison and avoids cross-strategy state pollution.

---

## 7) Main Technical Risks / Failure Modes

1. **Engine/app state drift** (orders/fills mismatch)
   - Mitigate via idempotent upserts + periodic reconciliation loops.

2. **WebSocket drops / stale order book**
   - Mitigate via heartbeat, sequence checks, auto-resync and snapshot reload.

3. **PnL discrepancies across screens**
   - Mitigate with single canonical performance calc module.

4. **Over-coupling to Freqtrade internals**
   - Mitigate with strict adapter boundary + canonical DB ownership.

5. **Premature distributed complexity**
   - Mitigate by modular monolith for MVP.

6. **Control race conditions (pause/stop during execution)**
   - Mitigate with explicit state machine + command queue semantics.

---

## 8) Phased Build Plan (Clean + Safe)

## Phase 0 — Foundations (1-2 days)
- Repo structure, core models, migration scaffolding
- ExecutionEngine interface + no-op stub
- Control plane skeleton and health endpoints

## Phase 1 — Market Data Core (2-4 days)
- Kraken ingest (SOL/USD)
- Candles/trades/order book persistence
- Market data UI view + live stream

## Phase 2 — Single Strategy E2E Paper Trading (3-5 days)
- Freqtrade adapter integration in paper mode
- One strategy instance end-to-end
- Orders/fills/positions + trade history UI

## Phase 3 — Multi-Strategy Isolation (3-5 days)
- Add trend, mean reversion, breakout strategies
- Separate portfolios per strategy
- Strategy comparison screen + control toggles

## Phase 4 — Reliability Hardening (2-4 days)
- Reconciliation jobs, restart recovery, audit trails
- Better error surfacing and operational tooling

## Phase 5 — Multi-Coin Activation Path (later)
- Add config-driven market registry
- Enable additional USD quote pairs without schema/API redesign

---

## 9) Future Path: Additional Coins + Futures

Design now to avoid rewrite later:
- Market identity is `(venue, symbol, instrument_type, quote_currency)`.
- Strategy interfaces accept `market_id` (not hardcoded SOL/USD).
- Portfolio layer supports spot now but already stores optional margin/leverage metadata.
- ExecutionEngine interface remains broker/exchange-agnostic.
- Future “strategy-manager/agent layer” is **advisory-only** unless explicit human approval gates are added.

---

## 10) Major Design Tradeoffs (Opinionated)

1. **Modular monolith vs microservices**
   - Choose modular monolith now: simpler deploy/debug, faster iteration.

2. **Canonical domain DB vs Freqtrade-native DB**
   - Choose canonical DB now: decouples product from engine.

3. **Per-strategy isolated capital vs shared portfolio realism**
   - Choose isolation now: cleaner analytics and safer behavior.

4. **Event-driven internals vs direct sync calls only**
   - Choose light eventing now: better observability and future scalability.

5. **Build for spot only vs future-proof schema**
   - Build spot behavior now, but future-proof core schema/interfaces.

---

## Suggested Monorepo Layout

```text
krakbot/
  backend/
    app/
      api/
      core/
      domain/
      adapters/
        execution/
          freqtrade/
        marketdata/
          kraken/
      services/
        orchestrator/
        portfolio/
        performance/
      events/
      db/
        models/
        migrations/
      workers/
  frontend/
    src/
      pages/
      components/
      features/
      services/
      store/
  deploy/
    docker-compose.yml
```

This is intentionally biased toward a **clean MVP** that still preserves a realistic expansion path.
