# Confidence-Semantics Pass Report (Narrow)

Date: 2026-03-18/19  
Branch: `main`

Scope constraints respected:
- kept stricter breakout discipline
- did not loosen policy thresholds
- did not change live defaults
- did not switch models
- no new features/data sources

## Exact prompt/output behavior changes made

Implemented in `backend/app/services/models/qwen_local_adapter.py`.

1. **Removed broad no-trade inflation rule from prior pass**
   - Removed the direct conversion rule that forced `action -> no_trade` under broad risk predicates.

2. **Introduced explicit confidence semantics bands**
   - **high** confidence only for clean, strong-edge setups
   - **mid** confidence for imperfect but tradable setups
   - **low** confidence for weak-edge setups

3. **Kept strict breakout discipline**
   - `breakout_confirmation` remains gated by strong evidence requirements (`breakout_strong`).

4. **Confidence score computation changed to edge-minus-risk semantics**
   - Edge combines momentum/tradability/contradiction cleanliness.
   - Risk combines contradiction/extension/freshness deficit/fragility.

5. **Schema behavior unchanged and valid**
   - no contract regressions detected.

---

## Controlled before/after windows

Each side analyzed over 500-row recent windows.

### BEFORE (pre semantics pass)
- actions:
  - long 138
  - short 124
  - no_trade 238
- setup_type:
  - breakout_confirmation 32
  - mean_reversion 178
  - trend_continuation 52
  - unclear 238
- confidence bucket frequencies (trade actions only):
  - low 2
  - mid 210
  - high 50

Bucket quality:
- low: acc15 50.0% (n=2), acc1h 100% (n=2; tiny sample)
- mid: acc15 37.3% (n=204), acc1h 51.0% (n=194)
- high: acc15 50.0% (n=50), acc1h 45.8% (n=48)

### AFTER (post semantics pass)
- actions:
  - long 155
  - short 134
  - no_trade 211
- setup_type:
  - breakout_confirmation 10
  - mean_reversion 228
  - trend_continuation 51
  - unclear 211
- confidence bucket frequencies (trade actions only):
  - low 8
  - mid 236
  - high 45

Bucket quality:
- low: acc15 50.0% (n=8), acc1h 71.4% (n=7; small sample)
- mid: acc15 40.0% (n=230), acc1h 48.6% (n=214)
- high: acc15 30.2% (n=43), acc1h 44.7% (n=38)

---

## Interpretation

### 1) Confidence bucket frequencies
- High bucket became slightly rarer (50 -> 45), but not dramatically.
- Low bucket became less sparse (2 -> 8), closer to intended semantics.

### 2) Confidence bucket quality
- Desired result (high > mid) was **not achieved**.
- High-confidence quality worsened on 15m and remained below mid on 1h.
- Mid bucket remains the most stable and meaningful in practice.

### 3) Setup distribution / breakout discipline
- Breakout frequency dropped further (32 -> 10).
- This keeps strict discipline, but may now be too restrictive.

### 4) Unclear/no_trade normalization
- no_trade/unclear reduced from 238 to 211.
- This is a modest normalization in the right direction.

### 5) Output stability
Schema validity checks passed (no invalid outputs observed).

---

## Recommendation: keep or revert?

**Recommendation: partial revert / adjust (do not keep as-is).**

Keep:
- stricter breakout gating concept.

Adjust/revert:
- current confidence-band mapping should be revised, because high-confidence outcomes are not more meaningful than mid.
- specifically, avoid assigning high confidence from rule thresholds that are not empirically separating quality.

Practical next step (still narrow):
- keep breakout gate strict,
- remap confidence so high is assigned only when historical separators are strongest,
- target: high bucket 1h quality >= mid bucket before accepting.
