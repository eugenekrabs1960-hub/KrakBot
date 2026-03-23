# Hyperliquid regime-actionability limit-test update

## Short changelog
- Added new Hyperliquid-first limit-test family: `hl_regime_actionability_limit_test_v1` (momo learner only).
- Added bounded regime-actionability knobs to editable Hyperliquid experiment surface.
- Added phased limit-test logic (probe -> escalate -> rollback) with config-driven thresholds.
- Added anti-dead-end memory in mutation planner:
  - rotates hypothesis after repeated blocker persistence
  - avoids repeating equivalent deltas
- Added non-actionable WAIT tracking for explicit bottleneck measurement.
- Kept mutation mode framework intact: `normal_adaptive` and `limit_test`.

## Config/schema additions
- `autonomy_config.hyperliquid_limit_test.*`
  - `enabled`, `family`, `phase`, `phase_1_min_observation_runs`, `same_blocker_rotate_after`
  - `goals[]`
  - `thresholds.*`
  - `rollback.*`
  - `bounds.*`
- `hyperliquid_overrides.hl_15m_trend_follow_momo_gate_v1.*`
  - `actionable_confidence_min`
  - `neutral_regime_participation_allow`
  - `min_regime_strength_for_probe_entries`
  - `max_probe_risk_fraction`
  - `leverage_cap_during_probe_phase`
  - `leverage_escalation_gate_enabled`

## Initial parameter ranges
- `actionable_confidence_min`: 0.45 .. 0.70 (step 0.03)
- `neutral_regime_participation_allow`: false/true (default false)
- `min_regime_strength_for_probe_entries`: 0.35 .. 0.65 (step 0.05)
- `max_probe_risk_fraction`: 0.20 .. 0.60 (step 0.10)
- `leverage_cap_during_probe_phase`: 1.5 .. 4.0 (step 0.5)
- `leverage_escalation_gate_enabled`: false/true (default false)

## Escalation criteria (default)
- observation window >= 3 family runs
- non-actionable WAIT ratio improvement >= 0.10
- actionable ratio improvement >= 0.08
- expectancy net delta >= -0.03
- fee drag pct delta <= +20

## Rollback criteria (default)
- expectancy net delta < -0.05
- fee drag pct delta > +30
- non-actionable WAIT ratio regression > 0.07
- actionable ratio drop > 0.05

## Example experiment log entry
```json
{
  "ts": "2026-03-23T22:10:00Z",
  "mutation": {
    "domain": "hyperliquid",
    "mode": "hl_15m_trend_follow_momo_gate_v1",
    "param": "neutral_regime_participation_allow",
    "old": false,
    "new": true,
    "mutation_mode": "limit_test",
    "limit_test_goal": "validate_probe_phase_before_escalation",
    "limit_test_family": "hl_regime_actionability_limit_test_v1",
    "limit_test_phase": "phase_1_probe_only",
    "anti_dead_end": {
      "same_blocker_persistence": 3,
      "rotate_after": 3,
      "rotated_hypothesis": true,
      "blocked_reason": "No futures entry: regime not actionable for controlled simulator."
    }
  },
  "analyses": [
    {
      "mode": "hl_15m_trend_follow_momo_gate_v1",
      "non_actionable_wait_ratio": 0.78,
      "action_ratio": 0.09,
      "expectancy_net": -0.11,
      "fee_drag_pct": 168.2
    }
  ]
}
```

## 24h monitoring checklist
- Confirm active bots set remains exactly 4 expected keys.
- Verify every applied HL mutation targets only `hl_15m_trend_follow_momo_gate_v1`.
- Track `non_actionable_wait_ratio` trend every cycle.
- Track `action_ratio` trend every cycle.
- Watch `expectancy_net` and `fee_drag_pct` for rollback thresholds.
- Check anti-dead-end metadata appears on repeated blocker runs.
- Ensure `leverage_escalation_gate_enabled=false` during phase 1.
- Verify no live/private routing flags changed (paper-only remains true).
