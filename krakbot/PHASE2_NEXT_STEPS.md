# Krakbot Phase 2 Status

## Implemented

- Strategy registry and strategy instance creation with isolated paper portfolios.
- Durable orchestrator state machine persisted in `system_state`.
- Canonical execution tables (`orders`, `executions`) and adapter normalization path.
- New control endpoints for bot state and strategy toggle.
- New paper order endpoint through `FreqtradeExecutionAdapter`.

## API additions

- `GET /api/control/bot`
- `POST /api/control/bot`
- `POST /api/control/strategy/toggle`
- `POST /api/strategies/instances`
- `GET /api/strategies`
- `POST /api/trades/paper-order`

## Next (Phase 3)

1. Replace paper-sim fill in adapter with real Freqtrade bridge callbacks.
2. Add position + portfolio balance update logic per execution.
3. Add performance snapshot worker and strategy comparison metrics.
4. Add dashboard controls UI wiring.
