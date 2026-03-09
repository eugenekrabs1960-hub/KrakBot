# Krakbot Build Next Steps

## Immediate next actions (Phase 1)

1. Implement Kraken market ingestion service (trades + orderbook + candles).
2. Add canonical DB migrations for market data tables.
3. Add websocket endpoint `/api/ws` for live UI fanout.
4. Implement strategy registry and seed 3 MVP strategies:
   - trend_following
   - mean_reversion
   - breakout
5. Wire control commands into orchestrator state machine + persistence.

## Guardrails
- Keep all execution calls behind `ExecutionEngine`.
- Keep SOL/USD as config default, not hardcoded in code paths.
- Keep portfolio state isolated by `strategy_instance_id`.
