# Krakbot Progress + Next Steps

## Phase 1 status (completed)

- [x] Kraken market ingestion service (trade + orderbook)
- [x] Canonical market tables + SQL migration (`app/db/migrations/0001_market_data.sql`)
- [x] Live websocket endpoint for UI fanout (`/api/ws`)
- [x] 1m candle aggregation from trade stream

## Phase 2 immediate actions

1. Add strategy registry persistence (`strategies`, `strategy_instances`).
2. Implement orchestrator command state machine with durable state transitions.
3. Wire Freqtrade adapter to paper execution callbacks and order/fill normalization.
4. Build dashboard widgets against real market endpoints.
5. Add integration tests for ingest + candle formation.

## Guardrails
- Keep all execution calls behind `ExecutionEngine`.
- Keep SOL/USD as config default, not hardcoded in code paths.
- Keep portfolio state isolated by `strategy_instance_id`.
