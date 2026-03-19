# Confidence Calibration Pass (Breakout Discipline Focus)

Date: 2026-03-18/19  
Branch: `main`  
Scope constraints respected:
- no safety-threshold loosening
- no live-default changes
- no model switch
- no new features/data sources

## Exact prompt/output behavior changes made

This repo uses deterministic local-analyst behavior rules (adapter) rather than external prompt text files.
Equivalent "prompt behavior" changes were implemented in:
- `backend/app/services/models/qwen_local_adapter.py`

### Changes introduced

1. **Confidence penalties strengthened** (core calibration rule)
   - confidence now penalized by weighted risk factors:
     - contradiction
     - extension
     - low freshness
     - fragility

2. **High-confidence gating tightened**
   - high confidence (>=0.70) is clipped unless packet risk context is clean:
     - contradiction low
     - extension low
     - freshness high
     - fragility low

3. **Breakout discipline tightened**
   - `breakout_confirmation` now requires stronger combined evidence:
     - `breakout_state == confirmed`
     - strong momentum
     - trend alignment + trend quality
     - low contradiction/extension
     - acceptable freshness/liquidity

4. **Modest no_trade bias for ambiguous/risky packets**
   - if risk/ambiguity high (e.g., contradiction/extension/freshness/fragility), trade intents are converted to `no_trade` more often.

5. **Schema stability preserved**
   - reason/risk cardinality and invalidation requirements unchanged and satisfied.

---

## Evaluation setup

- controlled large window before pass: 500 decisions (`/tmp/conf_before.json`)
- controlled large window after pass: 500 decisions (`/tmp/conf_after.json`)
- paper mode, live disarmed, no threshold loosening

---

## Before/after confidence bucket performance

### BEFORE (trade actions only)
- low: 9 | acc15=33.3% | acc1h=50.0%
- mid: 274 | acc15=42.0% | acc1h=45.9%
- high: 121 | acc15=43.7% | acc1h=41.3%

### AFTER (trade actions only)
- low: 4 | acc15=25.0% | acc1h=75.0% (tiny sample)
- mid: 244 | acc15=37.8% | acc1h=50.0%
- high: 86 | acc15=43.5% | acc1h=41.5%

### Read
- high-confidence count dropped materially (**121 -> 86**, ~29% reduction).
- high-confidence 1h quality remains below mid bucket, so calibration improved in frequency discipline but still not ideal in quality separation.

---

## Before/after setup_type distribution

### BEFORE
- breakout_confirmation: 141
- mean_reversion: 177
- trend_continuation: 86
- unclear: 96

### AFTER
- breakout_confirmation: 79
- mean_reversion: 179
- trend_continuation: 76
- unclear: 166

### Read
- breakout_confirmation frequency dropped strongly (**141 -> 79**), indicating tighter breakout discipline.
- unclear/no_trade contexts increased (more conservative handling of ambiguous packets).

---

## Breakout quality before/after

(Trade actions with `setup_type=breakout_confirmation`)

### BEFORE
- count: 141
- acc15: 41.7%
- acc1h: 43.5%

### AFTER
- count: 79
- acc15: 39.7%
- acc1h: 48.7%

### Read
- breakout calls are much fewer.
- 1h breakout quality improved; 15m slightly lower.
- net effect is a more selective breakout policy with better medium-horizon signal quality.

---

## Did no_trade increase modestly in appropriate cases?

- no_trade count: **96 -> 166**

This increase is meaningful (not tiny). It reflects deliberate risk-penalty behavior.
Given unchanged safety thresholds and improved breakout selectivity, this is directionally appropriate for a calibration pass, though it should be watched for excess passivity.

---

## Gate-distribution side effect (observed)

- allow_trade: 92 -> 45
- block_market_conditions: 187 -> 137
- block_risk: 125 -> 152
- downgrade_to_watch: 96 -> 166

Interpretation:
- confidence/prompt-side conservatism shifted flow toward no_trade/downgrade and away from market blocks.
- this is expected from stricter decision discipline, not threshold changes.

---

## Schema validity/stability check

After pass:
- invalid reasons<2: 0
- invalid risks<1: 0
- missing invalidation on trade actions: 0
- confidence out of range: 0

Stable output behavior preserved.

---

## Conclusion

- High-confidence decisions became **rarer**.
- Breakout_confirmation became **much less frequent** and **more selective**.
- 1h breakout quality improved; high-confidence quality separation is still not fully solved.
- no_trade rose substantially, improving caution but requiring monitoring for over-passivity.

Overall: this pass achieved the intended calibration direction without changing safety thresholds or live defaults.
