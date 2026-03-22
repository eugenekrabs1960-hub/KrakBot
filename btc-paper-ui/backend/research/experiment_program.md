# experiment_program.md

Goal: improve paper-only mode performance with small, reversible edits while keeping evaluator fixed.

## Frozen boundary (do not edit in normal cycles)
- `btc-paper-ui/backend/main.py` evaluator outputs and logic:
  - baseline comparator
  - regime recommendations
  - mode review recommendations
  - regime policy summaries
- Live/private trading behavior (must remain paper-only)

## Editable surface (phase 1)
Only edit values in `btc-paper-ui/backend/research/experiment_surface.json`.

Allowed keys:
- `kraken_overrides.<mode>.rr_min`
- `kraken_overrides.<mode>.fee_bps_entry`
- `kraken_overrides.<mode>.fee_bps_exit`
- `kraken_overrides.<mode>.enable_time_exit`
- `kraken_overrides.<mode>.max_bars_open`
- `kraken_overrides.<mode>.max_minutes_open`

Allowed mode for autonomous mutation (single learner):
- `btc_15m_conservative_netedge_v1`

Tracked but not mutated by autonomous loop:
- Kraken baseline reference: `btc_15m_conservative`
- Hyperliquid learner monitor: `hl_15m_trend_follow_momo_gate_v1`
- Diagnostic/secondary Kraken modes: inverse + breakout

## One-cycle loop
1. Read `/api/state` (fixed evaluator) and `/api/hyperliquid/state`.
2. Score each non-baseline Kraken experiment:
   - comparator verdict (primary)
   - mode review status
   - expectancy_net, fee_drag, sample size
3. Keep/discard recommendation:
   - keep if comparator in {PROMOTE_CANDIDATE, KEEP_TESTING}
   - probation if comparator is PROBATION
   - discard-watch if comparator is DISCARD_CANDIDATE
   - inconclusive if comparator is INSUFFICIENT_DATA
4. If `--apply`:
   - mutate only one parameter on one inconclusive/weak candidate by a small step
   - write update to `experiment_surface.json`
5. Append run report to `experiment_runs.jsonl`.

## Mutation policy (small-step)
- For breakout mode: adjust `rr_min` by -0.05 (floor 1.10) when no-edge/over-filtering pattern dominates.
- For netedge/inverse: adjust `rr_min` by -0.05 (mode-specific floor) only when sample is low and comparator is inconclusive.
- Never change baseline mode in autonomous cycle.

## Safety
- No direct source-code edits in autonomous cycles.
- No evaluator changes.
- No live order routes.
