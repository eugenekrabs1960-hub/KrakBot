# Krakbot Phase 5 Status (Multi-coin Activation Path)

## Implemented

- Added config-driven market registry tables:
  - `market_registry`
  - `strategy_markets`
- Seeded Kraken USD spot markets:
  - SOL/USD (enabled)
  - BTC/USD (disabled by default)
  - ETH/USD (disabled by default)
- Added market registry service + API routes:
  - `GET /api/markets`
  - `POST /api/markets`
  - `POST /api/markets/{market_id}/toggle`
  - `POST /api/markets/assign`
- Kraken ingestor now subscribes using enabled market registry symbols (with env fallback).
- Frontend now has a simple Market Registry view with enable/disable controls.

## Why this matters

This enables adding new USD pairs with no schema/API redesign and keeps SOL/USD as the default first market.

## Next

1. Support per-strategy multi-market activation from `strategy_markets`.
2. Add guardrails for maximum enabled markets in MVP to avoid overload.
3. Add futures-ready market metadata fields and validation constraints.
4. Add UI filtering and strategy-market assignment controls.
