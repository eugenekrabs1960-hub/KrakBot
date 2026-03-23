# experiment_program.md

Goal: improve paper-only mode performance with Hyperliquid-first autonomous learning while keeping evaluator fixed.

## Frozen boundary (do not edit in normal cycles)
- `btc-paper-ui/backend/main.py` evaluator outputs and logic:
  - baseline comparator
  - regime recommendations
  - mode review recommendations
  - regime policy summaries
- Live/private trading behavior (must remain paper-only)

## Runtime scope constraints (must hold)
Active bots remain exactly:
- `btc_15m_conservative` (frozen)
- `btc_15m_conservative_netedge_v1` (Kraken learner)
- `hl_15m_trend_follow` (frozen/shadow)
- `hl_15m_trend_follow_momo_gate_v1` (Hyperliquid learner)

Retired bots remain retired from default runtime/UI.
News remains context-only, never direct buy/sell commanding.

## Editable surface (phase 1)
Only edit values in `btc-paper-ui/backend/research/experiment_surface.json`.

Allowed keys:
- `kraken_overrides.<mode>.rr_min`
- `kraken_overrides.<mode>.fee_bps_entry`
- `kraken_overrides.<mode>.fee_bps_exit`
- `kraken_overrides.<mode>.enable_time_exit`
- `kraken_overrides.<mode>.max_bars_open`
- `kraken_overrides.<mode>.max_minutes_open`
- `hyperliquid_overrides.hl_15m_trend_follow_momo_gate_v1.momentum_gate_min_atr_body`
- `hyperliquid_overrides.hl_15m_trend_follow_momo_gate_v1.actionable_confidence_min`
- `hyperliquid_overrides.hl_15m_trend_follow_momo_gate_v1.neutral_regime_participation_allow`
- `hyperliquid_overrides.hl_15m_trend_follow_momo_gate_v1.min_regime_strength_for_probe_entries`
- `hyperliquid_overrides.hl_15m_trend_follow_momo_gate_v1.max_probe_risk_fraction`
- `hyperliquid_overrides.hl_15m_trend_follow_momo_gate_v1.leverage_cap_during_probe_phase`
- `hyperliquid_overrides.hl_15m_trend_follow_momo_gate_v1.leverage_escalation_gate_enabled`

## Limit-test family (Hyperliquid-first)
Family name:
- `hl_regime_actionability_limit_test_v1`

Target:
- `hl_15m_trend_follow_momo_gate_v1` only

Mutation modes:
- `normal_adaptive`
- `limit_test`

Limit-test goals:
- `unblock_regime_actionability`
- `reduce_wait_from_non_actionable_regime`
- `validate_probe_phase_before_escalation`

## Phased guardrail logic
- Phase 1 (`phase_1_probe_only`):
  - probe-only participation (small size, bounded risk, low leverage cap)
  - leverage escalation gate disabled
- Phase 2 (`phase_2_escalation`):
  - escalate only after minimum observation window and pass thresholds
- Phase 3 (`phase_3_rollback`):
  - de-escalate/rollback when quality weakens

Default pass thresholds (config-driven):
- meaningful improvement in non-actionable WAIT ratio
- meaningful improvement in actionable ratio
- no material worsening in expectancy
- no material worsening in fee drag
- no worsening in blocker persistence
- minimum observation window before escalation

Default rollback triggers (config-driven):
- expectancy drops materially
- fee drag rises materially
- non-actionable WAIT ratio regresses
- actionable ratio degrades

## Anti-dead-end memory
- if same blocker persists after N tests in this family, rotate hypothesis parameter choice
- avoid repeating equivalent deltas already tried in this family

## One-cycle loop
1. Read `/api/state` (fixed evaluator) and `/api/hyperliquid/state`.
2. Score non-baseline learners.
3. Hyperliquid learner gets priority over Kraken learner for mutation choice.
4. Build one bounded mutation for one learner.
5. If `--apply`, write to `experiment_surface.json`.
6. Append run report to `experiment_runs.jsonl`.

## Safety
- No direct source-code edits in autonomous cycles.
- No evaluator changes.
- No live order routes.
