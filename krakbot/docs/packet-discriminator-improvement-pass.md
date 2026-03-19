# Packet Discriminator Improvement Pass (Narrow)

Date: 2026-03-18/19  
Branch: `main`

Scope respected:
- improved deterministic packet/meta discriminators using existing data only
- kept strict breakout discipline
- no safety-threshold loosening
- no live default changes
- no new external data sources

## Exact packet/meta fields revised

No schema expansion was added. Existing fields were revised to carry stronger discriminative meaning.

### Revised in `ml_scores` (existing fields)
File: `backend/app/services/features/ml_scores.py`

1. `contradiction_score` (revised)
   - Now combines multi-horizon return conflict + trend misalignment.
   - Purpose: better low-conflict vs high-conflict separation.

2. `trade_quality_prior` (revised)
   - Now combines asymmetry quality + trend cleanliness + breakout quality + low contradiction.
   - Purpose: better good-asymmetry vs poor-asymmetry separation.

3. `regime_compatibility_score` (revised)
   - Now reflects consistency among trend cleanliness, breakout quality, and contradiction.
   - Purpose: cleaner setup compatibility signal.

4. `extension_score` (revised)
   - Now combines proximity-to-range-extremes + return extension.
   - Purpose: distinguish clean continuation from late/extended continuation.

5. `fragility_score` (revised)
   - Now combines freshness deficit + source health deficit + realized volatility.
   - Purpose: explicit weak-context penalty in packet layer.

6. `crowdedness_score` (revised)
   - Now uses OI change + funding-state crowding proxy + book imbalance.
   - Purpose: distinguish crowded vs uncrowded opportunities.

7. `attention_score`, `opportunity_score`, `tradability_score` (revised)
   - Reweighted to depend on asymmetry/trend/breakout quality and execution quality.

8. `market_regime`, `move_probability_*`, `no_trade_prior` (revised)
   - Derived from revised discriminator stack for coherent semantics.

### Revised in packet change summary
File: `backend/app/services/features/packet_builder.py`

- `_snapshot_numeric` now tracks:
  - `trade_quality_prior`
  - `regime_compatibility_score`
- `change_summary.new_risks` can now emit:
  - `asymmetry_quality_degraded`
  - `regime_compatibility_degraded`

Purpose:
- make packet-level change diagnostics directly reflect setup-quality discriminators.

---

## Rationale by target distinction

1. **Clean continuation vs noisy continuation**
- improved via `trend_cleanliness` effects embedded in `regime_compatibility_score`, `contradiction_score`, and revised `trade_quality_prior`.

2. **Clean breakout vs weak breakout**
- improved via explicit `breakout_quality` decomposition (breakout_state + level proximity + micro/depth quality).

3. **Good asymmetry vs poor asymmetry**
- improved via `asymmetry_quality` embedded in `trade_quality_prior` and `opportunity_score`.

4. **Low conflict vs high conflict**
- improved via multi-horizon return conflict + alignment-derived `contradiction_score`.

---

## Before/after evaluation (same paper quality evaluation)

### Before (from prior confidence-semantics baseline)
Source: `/tmp/sem_after_metrics.json`

- actions:
  - long 155
  - short 134
  - no_trade 211
- setup_type:
  - mean_reversion 228
  - trend_continuation 51
  - breakout_confirmation 10
  - unclear 211
- confidence bucket frequencies (trade actions):
  - low 8
  - mid 236
  - high 45
- bucket performance:
  - low: 15m 50.0% (n=8), 1h 71.4% (n=7; tiny)
  - mid: 15m 40.0% (n=230), 1h 48.6% (n=214)
  - high: 15m 30.2% (n=43), 1h 44.7% (n=38)

### After packet-discriminator improvements
Source: `/tmp/packet_after_metrics.json`

- actions:
  - long 183
  - short 166
  - no_trade 151
- setup_type:
  - mean_reversion 271
  - trend_continuation 69
  - breakout_confirmation 9
  - unclear 151
- confidence bucket frequencies (trade actions):
  - low 35
  - mid 270
  - high 44
- bucket performance:
  - low: 15m 38.7% (n=31), 1h 48.3% (n=29)
  - mid: 15m 43.8% (n=267), 1h 48.4% (n=244)
  - high: 15m 34.9% (n=43), 1h 47.6% (n=42)

---

## Interpretation

1. **Setup distribution**
- Breakout remains strict and rare (10 -> 9), as intended.
- `unclear/no_trade` normalized downward (211 -> 151), reducing excess inflation.

2. **Confidence separation**
- 15m: mid improved and remains best; high still not clearly superior.
- 1h: high nearly matches mid but does not clearly exceed.
- Separation improved somewhat in stability, but still not semantically ideal.

3. **Schema/output stability**
- no schema violations observed in sample.

---

## Recommendation

Yes — **confidence semantics should be revisited after this packet improvement**, but narrowly.

Reason:
- packet discriminators improved behavior (especially no_trade normalization and cleaner setup spread),
- but high-confidence bucket still does not consistently dominate mid bucket quality.

Suggested next narrow step:
- keep current packet discriminators,
- retune only high-band assignment rule to require stronger `trade_quality_prior` + low `contradiction/extension/fragility` jointly,
- avoid broad no-trade bias.
