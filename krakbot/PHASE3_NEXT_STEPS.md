# Krakbot Phase 3 Status

## Implemented

- Added position model + portfolio balance history + strategy events tables.
- Added portfolio engine to apply fills to isolated per-strategy positions/equity.
- Added performance snapshot recomputation after each execution.
- Upgraded Freqtrade adapter to:
  - optionally call real Freqtrade REST bridge (if configured)
  - fallback to simulated paper fills when bridge is unavailable
  - always normalize into canonical `orders`/`executions`
- Strategy comparison API now includes current position + equity.
- UI controls page now sends bot lifecycle commands.
- UI strategy comparison now shows live metrics rows.

## To finish next

1. Replace `forceenter` bridge path with full trade lifecycle sync from Freqtrade events.
2. Add sell-side realized PnL at execution row granularity (currently position-level canonical realized is authoritative).
3. Add periodic snapshot scheduler independent of order events.
4. Add integration tests for state transitions + portfolio math.
