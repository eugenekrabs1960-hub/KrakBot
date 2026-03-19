# Paper Tuning Pass Report (Validation-Driven)

Date: 2026-03-18/19
Branch: `main`
Scope followed exactly:
1) paper-profile policy thresholds
2) re-run validation with before/after
3) narrow prompt/output improvement
4) deterministic `change_summary` improvement

No unrelated features added. Live-mode safety defaults untouched.

---

## Supervisor note
- Supervisor automation remains disabled in this lab path.
- `jason` exists in repo as an agent, but not wired as active supervisor automation here.

---

## Test protocol (controlled windows)
- Forced mode: `paper`
- `live_armed=false`
- `trading_enabled=true`
- temporarily set `loop.decision_cycle_seconds=3600` to reduce background decision-loop interference during measurement windows
- each window = 30 manual cycles (~90 packet/decision/policy rows)
- paper positions flattened before each window: `POST /api/execution/flatten-all`

Data windows used:
- **Before policy tuning**: `/tmp/metrics_before_controlled.json`
- **After policy tuning (before prompt/change_summary work)**: `/tmp/metrics_after_controlled.json`
- **After full pass (policy + prompt + change_summary)**: `/tmp/metrics_after_full.json`

---

## 1) Policy tuning pass (paper-profile thresholds first)

### Exact threshold changes made
File: `backend/app/core/config.py`

- `min_liquidity_score`: **0.25 -> 0.20**
- `min_freshness_score`: **new 0.30** (replacing hardcoded 0.40 behavior)
- `max_volatility_rv_1h`: **new 0.95** (replacing hardcoded 0.90 behavior)
- `max_contradiction`: **0.70 -> 0.85**
- `max_crowdedness`: **0.80 -> 0.85**
- `max_extension`: **0.85 -> 0.90**

File: `backend/app/services/policy/checks.py`
- moved from hardcoded constants to config-driven thresholds above.

### Before vs after (policy-only window)

#### Action counts (long / short / no_trade)
- **Before**: long 35 / short 32 / no_trade 23
- **After**:  long 34 / short 41 / no_trade 15

#### Gate counts (allow / downgrade / block)
- **Before**:
  - allow_trade: 4
  - downgrade_to_watch: 23
  - blocks total: 63 (market 32 + risk 31)
- **After**:
  - allow_trade: 5
  - downgrade_to_watch: 15
  - blocks total: 70 (market 34 + risk 36)

#### Most common block reasons
- **Before**:
  - `market_quality`: 32
  - `portfolio_limits`: 31
- **After**:
  - `portfolio_limits`: 36
  - `market_quality`: 34

#### Trade-through rate
- definition: `allow_trade / requested_action!=no_trade`
- **Before**: 4 / 67 = **5.97%**
- **After**: 5 / 75 = **6.67%**

Interpretation:
- modest improvement in trade-through, but still very passive.
- main bottleneck shifted more clearly to `portfolio_limits` (position cap saturation in paper when no closes occur).

---

## 2) Prompt/output improvement pass (narrow)

File changed:
- `backend/app/services/models/qwen_local_adapter.py`

What changed (narrowly):
- kept deterministic schema-compliant output contract
- made reasons/risks evidence-specific using packet fields
- varied thesis summary with packet metrics
- setup_type now derives from structure/trend context rather than fixed string
- evidence_used references expanded packet paths

Validation after full pass (90-decision window):
- invalid reasons<2: 0
- invalid risks<1: 0
- invalid trade missing invalidation: 0
- invalid confidence range: 0
- thesis unique count: **90** (was effectively 1 previously)
- unique reason labels: **4**
- unique risk labels: **4**

Conclusion:
- output validity preserved
- reasoning specificity/coherence improved materially.

---

## 3) Deterministic `change_summary` improvement

File changed:
- `backend/app/services/features/packet_builder.py`

What changed:
- added per-coin deterministic delta tracking across consecutive packets
- `largest_feature_changes` now populated with top absolute deltas
- `new_risks` now populated on threshold crossings (contradiction/extension/liquidity/volatility)

Validation (90-packet window):
- `change_summary_nonbaseline`: **90/90**
- `change_summary_with_new_risks`: **28/90**

Conclusion:
- packet delta context is now populated and usable for analyst reasoning.

---

## 4) Final behavior snapshot (after full pass)

From latest 90-row window:

### Actions
- long: 34
- short: 33
- no_trade: 23

### Gate outcomes
- allow_trade: 6
- downgrade_to_watch: 23
- block_market_conditions: 36
- block_risk: 25

### Most common block reasons
- `market_quality`: 36
- `portfolio_limits`: 25

### Trade-through rate
- requested trades: 67
- allowed: 6
- trade-through: **8.96%**

Interpretation:
- moved from overly passive toward modestly more active, but still conservative.
- improvements came without schema-validity regressions.

---

## Notes on passivity/aggressiveness
- System remains on the conservative side in paper mode.
- Compared with initial pre-tune behavior, trade-through improved but is still low.
- Current dominant blockers are market quality and portfolio limits.

---

## Artifacts
- before/after metrics files generated during run:
  - `/tmp/metrics_before_controlled.json`
  - `/tmp/metrics_after_controlled.json`
  - `/tmp/metrics_after_full.json`
- sample outputs added:
  - `docs/samples/paper_tuning_sample_feature_packets_after.json`
  - `docs/samples/paper_tuning_sample_decision_outputs_after.json`

---

## Minimal next tuning (if requested next)
1. keep policy strictness but reduce paper `portfolio_limits` saturation effect during evaluation windows (e.g., periodic flatten in test harness only, not product behavior change)
2. tighten prompt to explicitly cite top 2 `change_summary` deltas in reasons
3. keep live safety defaults unchanged
