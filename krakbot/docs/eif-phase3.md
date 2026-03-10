# EIF Phase 3 - Operator UI Integration + Safety Notes

Phase 3 focuses on making EIF data usable by operators in existing MVP pages (no redesign), with explicit disabled/error states and simple rollback controls.

## UI surfaces

- **Dashboard**
  - EIF summary card with current regime, skip ratio, top reason code.
  - Shows clear disabled state if `EIF_ANALYTICS_API_ENABLED=false`.

- **Strategy Comparison**
  - Window selector (`rolling` / `baseline`) driven by scorecard `window_label`.
  - Sample-size/confidence cues and low-n exploratory indicator (`n < 20`).
  - By-market and by-regime slices when API returns data.

- **Trade History**
  - Decision trace visibility from `/api/eif/filter-decisions`:
    - allow/skip, reason code, precedence stage, regime snapshot id, trace chain.
  - Regime context visibility from `/api/eif/trade-trace` when context is present.

- **Controls**
  - EIF operator summary cards:
    - current regime snapshot count,
    - recent skip ratio,
    - top reason codes,
    - recent expectancy delta proxy.

## Operator workflow

### Why was this trade skipped?

1. Open **Trade History**.
2. Check **Decision Trace** row for `ALLOW/SKIP`, `reason_code`, and `precedence_stage`.
3. Confirm linked `regime_snapshot_id`.
4. Check trade-trace context regime payload if available.

### What changed in regime/expectancy?

1. Open **Strategy Comparison**.
2. Switch scorecard window (`rolling` vs `baseline`).
3. Compare sample size and expectancy for same strategy/market.
4. Review by-regime slice concentration changes.

## Rollback / kill-switch runbook

If EIF starts over-blocking or appears inconsistent, use flags (safe defaults are off):

1. **Immediate unblock (keep observability):**
   - `EIF_FILTER_ENFORCE_MODE=false`
   - `EIF_FILTER_SHADOW_MODE=true`
2. **Fail-open safety during unstable data feeds:**
   - `EIF_FILTER_FAIL_CLOSED=false`
3. **Disable analytics API if needed (UI will degrade gracefully):**
   - `EIF_ANALYTICS_API_ENABLED=false`
4. **Full capture off (last resort):**
   - `EIF_CAPTURE_ENABLED=false`
   - `EIF_SCORECARD_COMPUTE_ENABLED=false`

Verify active flags:

```bash
curl -s http://localhost:8010/api/control/eif-flags
```

Check data continuity after rollback:

```bash
curl -s http://localhost:8010/api/eif/summary
curl -s 'http://localhost:8010/api/eif/filter-decisions?limit=20'
```
