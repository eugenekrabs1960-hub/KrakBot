# Paper-Trading Behavior Validation Report

Date: 2026-03-18/19
Branch: `main`
Scope: validation/tuning analysis only (no new product features)

## Supervisor model status

- In current lab path, supervisor automation is still disabled.
- `jason` exists as an agent in repo, but **is not active supervisor automation in this flow** yet.
- This validation run used the current local analyst + policy pipeline in paper mode.

## Test setup

1. Forced paper-safe mode:
   - `execution_mode=paper`
   - `live_armed=false`
   - `trading_enabled=true`
2. Ran 30 additional manual decision cycles:
   - `POST /api/decisions/run-cycle`
3. Pulled recent records:
   - `GET /api/decisions/recent?limit=400`

Validation dataset snapshot:
- packets: 132
- decisions: 132
- policy decisions: 132
- execution records: 14

---

## A) FeaturePacket sanity + internal consistency

Checks performed across recent packets:
- coin/symbol consistency (`symbol` starts with `coin`)
- allowed actions include long/short/no_trade
- mode in {paper, live_hyperliquid}
- non-negative/non-zero key prices
- quality scores in expected range for liquidity/freshness
- move probabilities in [0,1]

Result summary:
- total_packets: 132
- mismatches/invalid range findings: **0** on all above checks

Conclusion:
- Packet structure appears internally consistent for tested sample.

---

## B) DecisionOutput validity

Validation checks over recent decisions:
- reasons length >= 2
- risks length >= 1
- confidence in [0,1]
- uncertainty in [0,1]
- trade actions require invalidation
- non-empty thesis
- non-empty evidence_used

Result summary:
- total decisions: 132
- invalid outputs found: **0**

Conclusion:
- No schema-invalid DecisionOutputs observed.

---

## C) Aggregate behavior counts

### Action counts (local analyst)
- long: **51**
- short: **44**
- no_trade: **37**

### Gate result counts (all recent)
- allow_trade: **14**
- downgrade_to_watch: **37**
- block_market_conditions: **62**
- block_risk: **18**
- block_mode_disabled: **1** (from earlier live-disarmed test)

### Paper-only gate counts
- allow_trade: **14**
- downgrade_to_watch: **32**
- block_market_conditions: **62**
- block_risk: **18**
- paper total: **126**

### Trade-through
- trade-request decisions (requested_action != no_trade): **94** (paper)
- allowed trades: **14** (paper)
- allow rate vs trade requests: **~14.9%**
- allow rate vs all paper decisions: **~11.1%**

Interpretation:
- The current system is **on the passive/overblocking side**.

---

## D) Reasoning quality/coherence observations

Observed behavior:
- thesis text unique count: **1**
  - always: `"Packet-driven setup evaluation"`
- reason labels are fixed and repetitive:
  - `momentum`, `tradability`
- risk label is fixed and repetitive:
  - `regime_shift`

Interpretation:
- Outputs are schema-valid and coherent structurally, but **reasoning diversity/diagnostic value is low**.
- This qualifies as a low-information explanation pattern, even when actions vary.

---

## E) Is system too passive or too aggressive?

- Analyst action mix is moderately active (95/132 trade intents if counting long+short).
- Policy gate blocks most non-no_trade intents.
- Net system behavior: **too passive due to gate strictness**, especially market-condition blocks.

---

## F) Invalid outputs occurring?

- No invalid outputs detected in tested dataset.
- DecisionOutput schema quality is stable in this run.

---

## G) Are trades actually getting through?

- Yes, but limited.
- 14 execution records observed in dataset window.
- Trade-through exists, but at low frequency relative to trade intents.

---

## H) Top 3 tuning opportunities (smallest next changes)

### 1) Policy threshold tuning (highest impact)
Problem:
- `block_market_conditions` dominates.

Small change:
- Relax one threshold at a time (paper only), e.g. min liquidity score and/or volatility cap.
- Re-measure allow rate target to ~20–35% of trade intents in paper.

### 2) Prompt/output behavior tuning for richer diagnostics
Problem:
- Explanations are repetitive and low-information.

Small change:
- Tighten prompt contract to require reason/risk labels drawn from packet-specific evidence buckets.
- Keep schema same; just improve reason specificity.

### 3) Packet change_summary quality improvement
Problem:
- `change_summary` currently mostly empty; model sees little explicit delta context.

Small change:
- Populate `largest_feature_changes` deterministically from prior packet deltas.
- No new data sources needed.

---

## Sample artifacts

- FeaturePackets:
  - `docs/samples/paper_validation_sample_feature_packets.json`
- DecisionOutputs:
  - `docs/samples/paper_validation_sample_decision_outputs.json`

---

## Overall conclusion

Current paper-mode pipeline is operational and schema-stable.
Primary issue is not invalid model output; it is **low-information reasoning + high gate rejection rate**.
Next tuning should stay narrow: policy threshold calibration first, then explanation quality, then packet delta context.
