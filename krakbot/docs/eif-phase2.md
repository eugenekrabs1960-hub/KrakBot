# EIF Phase 2 (Shadow-capable Filter Engine + Analytics API)

Phase 2 adds deterministic filter evaluation with optional enforcement and richer analytics endpoints.

## Feature flags (safe defaults)

All defaults are non-disruptive (`false`):

- `EIF_FILTER_SHADOW_MODE=false`
- `EIF_FILTER_ENFORCE_MODE=false`
- `EIF_FILTER_FAIL_CLOSED=false` (fail-open default for safety)
- `EIF_ANALYTICS_API_ENABLED=false`

Behavior:
- **Both shadow/enforce false:** no gating change in trading flow.
- **Shadow true:** evaluate + persist traces, but do not block orders.
- **Enforce true (and shadow false):** filter failures can block candidate execution.
- **Fail closed true:** evaluation errors block; otherwise fail-open allows and records `filter_eval_error`.

## Deterministic precedence

Rules are evaluated and blocked by this precedence order:
1. `data_integrity`
2. `hard_risk`
3. `setup_validity`
4. `soft_quality`

Final decision reason uses the first failed rule by precedence (stable tiebreak by `rule_id`).

## MVP rule set

- data staleness / health
- minimum volume / activity
- spread cap
- volatility floor/ceiling
- liquidity/depth minimum
- orderbook imbalance directional check
- regime-strategy compatibility
- cooldown on consecutive losses / drawdown shock

Each rule trace records:
- pass/fail
- measured values
- configured thresholds
- reason code

## Persistence updates

`eif_filter_decisions` now includes:
- `trace` (JSONB full rule trace)
- `precedence_stage`
- `shadow_mode`
- `enforce_mode`
- `filter_engine_version`

Migration: `backend/app/db/migrations/0009_eif_phase2_filter_engine.sql`

## Analytics API endpoints (read-only)

Enabled only when `EIF_ANALYTICS_API_ENABLED=true`.

- `GET /api/eif/summary`
- `GET /api/eif/regimes?market=&strategy_instance_id=&limit=&offset=`
- `GET /api/eif/filter-decisions?market=&strategy_instance_id=&reason_code=&limit=&offset=`
- `GET /api/eif/scorecards?market=&strategy_instance_id=&limit=&offset=`
- `GET /api/eif/trade-trace?market=&strategy_instance_id=&limit=&offset=`

Bounds:
- `limit` is clamped to `1..200` (except `events/recent` remains `1..500`)
- `offset >= 0`

## Example

```bash
curl -s http://localhost:8010/api/control/eif-flags
curl -s 'http://localhost:8010/api/eif/filter-decisions?market=SOL/USD&limit=20'
curl -s 'http://localhost:8010/api/eif/summary'
```
