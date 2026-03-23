# experiment_program.md

Goal: improve paper-only mode performance with Hyperliquid-first autonomous learning while keeping evaluator fixed.

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

Allowed learner modes for autonomous mutation (one target per cycle):
- `hl_15m_trend_follow_momo_gate_v1` (primary learner)
- `btc_15m_conservative_netedge_v1` (secondary support learner; near-frozen unless strong reason)

Tracked but never mutated by autonomous loop:
- Kraken baseline reference: `btc_15m_conservative`
- Hyperliquid baseline reference: `hl_15m_trend_follow`
- Retired variants are archive-only

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

## Mutation policy (aggressive-but-bounded)
- Hyperliquid learner first:
  - unblock dead-end cap states by increasing learner `max_positions` (bounded up to 4)
  - loosen `momentum_gate_min_atr_body` in larger steps when low-action dead-end persists
  - expand learner `max_leverage` gradually (bounded to 10x)
- Kraken learner remains secondary and near-frozen unless strong reason.
- News context influences mutation aggressiveness (cautious vs normal step), never direct trade commands.
- Mutate only one learner per cycle.
- Never change baseline mode in autonomous cycle.

## Safety
- No direct source-code edits in autonomous cycles.
- No evaluator changes.
- No live order routes.
