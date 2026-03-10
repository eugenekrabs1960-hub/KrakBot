# EIF Phase 1 (Data Foundation + Capture)

Phase 1 introduces shadow-mode data capture only. It does **not** enforce any filters or alter trading behavior.

## Feature flags (default OFF)

Backend settings:
- `eif.capture.enabled` -> env `EIF_CAPTURE_ENABLED=false`
- `eif.scorecard.compute.enabled` -> env `EIF_SCORECARD_COMPUTE_ENABLED=false`

Read current flags:
- `GET /api/control/eif-flags`

## Locked vocabulary artifacts (v1)

Implemented in `backend/app/services/eif_vocab.py`.

### Regime dimensions
- trend: `up | down | flat | unknown`
- volatility: `high | normal | low | unknown`
- liquidity: `thick | normal | thin | unknown`
- session_structure: `active | quiet | unknown`

### Filter decision reason codes
- decision: `ok | bot_not_running | strategy_disabled | hold_decision | no_market_trade_price | paper_only_guard | unknown`
- skip: `min_interval_guard | per_minute_rate_limit | bot_not_running | hold_decision | strategy_disabled | qty_non_positive | unknown`

### Trade context tags
- mode: `paper | live | test`
- event: `decision | entry | exit | skip | order_attempt | order_result`
- source: `live_paper_test_mode | api_paper_order | system`
- risk: `guarded | normal | unknown`

## New tables

Migrations:
- `backend/app/db/migrations/0007_eif_phase1_foundation.sql`
- `backend/app/db/migrations/0008_eif_phase1_1_integrity.sql` (adds `eif_filter_decisions.regime_snapshot_id` FK to `eif_regime_snapshots(id)`)

- `eif_regime_snapshots`
- `eif_trade_context_events`
- `eif_filter_decisions`
- `eif_scorecard_snapshots`

All tables are append-only and indexed for recent-by-strategy / recent-by-market reads.

## Phase 1 endpoints

- `GET /api/eif/summary`
- `GET /api/eif/events/recent?limit=50` (`limit` constrained to `1..500`, default `50`)

Endpoints are read-only and safe when empty/disabled.

## Scorecard note (Phase 1 placeholder)

In Phase 1, `expectancy` is a placeholder and currently equals `pnl_per_trade`.
The scorecard payload includes `expectancy_semantics=placeholder_equals_pnl_per_trade` and `expectancy_is_placeholder=true` to make this explicit.
