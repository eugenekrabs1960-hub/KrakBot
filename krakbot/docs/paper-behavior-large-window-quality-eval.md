# Paper Behavior Large-Window Decision Quality Evaluation

Date: 2026-03-18/19  
Branch: `main`  
Scope: quality analysis only. No threshold loosening. No live default changes. No new features.

## Window setup

- Mode forced to `paper`, `live_armed=false`
- Controlled run: 80 manual cycles added
- Dataset analyzed: last **500** decision rows (`/api/decisions/recent?limit=500`)

---

## 1) Action distribution (long/short/no_trade)

- long: **199** (39.8%)
- short: **197** (39.4%)
- no_trade: **104** (20.8%)

Observation:
- Directional calls are balanced long/short.
- no_trade fraction is moderate, not dominant.

---

## 2) setup_type distribution

- mean_reversion: **169** (33.8%)
- breakout_confirmation: **147** (29.4%)
- trend_continuation: **80** (16.0%)
- unclear: **104** (20.8%)

Observation:
- setup typing is not collapsed to a single class; decent spread.

---

## 3) Confidence-bucket performance (trade actions only)

Buckets:
- low: confidence < 0.40
- mid: 0.40–0.69
- high: >= 0.70

### 15m proxy directional accuracy
- low: **33.3%** (n=9)
- mid: **37.1%** (n=248)
- high: **34.6%** (n=133)

### 1h proxy directional accuracy
- low: **33.3%** (n=9)
- mid: **44.3%** (n=237)
- high: **40.7%** (n=123)

Key read:
- High confidence does **not** outperform mid confidence.
- Calibration appears imperfect (possible overconfidence in high bucket).

---

## 4) Gate result distribution

- allow_trade: **135** (27.0%)
- downgrade_to_watch: **104** (20.8%)
- block_market_conditions: **180** (36.0%)
- block_risk: **81** (16.2%)

Observation:
- still safety-first, but not frozen.

---

## 5) Basic proxy outcome quality by action type

### Long actions
- 15m directional accuracy: **34.7%** (n=196)
- 1h directional accuracy: **40.7%** (n=189)
- side-adjusted avg move:
  - 15m: **-0.000437%**
  - 1h: **-0.000823%**

### Short actions
- 15m directional accuracy: **37.6%** (n=194)
- 1h directional accuracy: **45.0%** (n=180)
- side-adjusted avg move:
  - 15m: **-0.000344%**
  - 1h: **-0.002827%**

Key read:
- Shorts perform slightly better than longs, but both are weak-to-moderate in this proxy.
- Quality issue appears upstream in decision quality, not just gate throughput.

---

## 6) Reasoning pattern analysis

Top reason-label pattern usage (trade actions):
1. `[momentum_alignment, execution_quality, structure_breakout_context]` -> **265** rows
2. `[momentum_alignment, execution_quality, trend_quality]` -> **131** rows

This indicates reasoning is still somewhat repetitive (two dominant templates).

Correlation with 1h proxy quality:
- structure_breakout_context pattern: **40.6%** (n=249)
- trend_quality pattern: **47.5%** (n=120)

Interpretation:
- breakout-context pattern correlates with weaker outcomes than trend-quality pattern in this sample.
- Reason template selection appears to matter and may be mis-weighted.

---

## 7) Top 3 improvements likely to raise decision quality (without loosening safety)

1. **Confidence calibration rule (model/prompt)**
   - Problem: high-confidence bucket underperforms mid bucket.
   - Improvement: cap confidence when contradiction/extension/freshness risk flags are elevated; enforce confidence penalty clauses in analyst output contract.

2. **Setup-type selection discipline (prompt/model logic)**
   - Problem: breakout-context reason template is frequent and lower quality.
   - Improvement: require stronger breakout confirmation conditions before `breakout_confirmation`; otherwise downgrade to `unclear` or `no_trade` more often.

3. **Packet-level discriminators for trend quality vs breakout noise (packet design)**
   - Problem: current packet may not sufficiently separate true breakout quality from transient moves.
   - Improvement: add deterministic breakout-quality subfeatures from existing data (no new source), and require explicit evidence reference for breakout calls.

---

## Conclusion

In this larger window, main weakness is **decision quality calibration**, not gate strictness alone.
The next quality gains should come from confidence/setup calibration and better packet discriminators, while keeping safety thresholds and live defaults unchanged.
