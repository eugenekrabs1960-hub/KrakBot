# High-Confidence Band Retune Report (Very Narrow)

Date: 2026-03-19  
Branch: `main`

Scope constraints respected:
- only high-confidence assignment logic changed
- packet discriminators kept as-is
- strict breakout discipline kept
- no threshold changes
- no live default changes
- no new data/features

## Exact logic changes for high-confidence assignment

File: `backend/app/services/models/qwen_local_adapter.py`

Changed only confidence-band gating in trade actions:

### Before
High confidence was allowed when:
- clean context and `abs(momentum) >= 0.55`

### After (retuned)
High confidence now requires **all** of:
- `clean == true`
- `abs(momentum) >= 0.68`
- `tradability >= 0.62`
- `contradiction <= 0.28`
- `extension <= 0.42`
- `freshness >= 0.62`
- `fragility <= 0.30`
- plus strong setup evidence:
  - `breakout_strong` **or** (`abs(trend_alignment) >= 0.72` and `trend_quality >= 0.70`)

High confidence range remains capped and narrow:
- `conf ∈ [0.72, 0.82]` when eligible

All non-high cases still map to existing mid/low logic.
No broad no-trade bias was added.

---

## Before/after confidence bucket frequencies

(Trade actions only)

### Before
- low: **68**
- mid: **291**
- high: **30**

### After
- low: **85**
- mid: **303**
- high: **10**

Read:
- high-confidence became much rarer (**30 → 10**, ~67% reduction).

---

## Before/after confidence bucket quality

### Before
- low: 15m **46.97%** (n=66), 1h **53.33%** (n=60)
- mid: 15m **47.55%** (n=286), 1h **50.36%** (n=274)
- high: 15m **53.33%** (n=30), 1h **50.00%** (n=30)

### After
- low: 15m **50.00%** (n=82), 1h **59.49%** (n=79)
- mid: 15m **51.34%** (n=298), 1h **50.88%** (n=283)
- high: 15m **70.00%** (n=10), 1h **70.00%** (n=10)

Read:
- high bucket now appears materially more meaningful in this sample.
- sample size for high is small (n=10), so monitor for stability in larger windows.

---

## Recommendation: is confidence now meaningful ranking signal?

**Tentatively yes** — with caution.

Why:
- high is now rare and aligns with better proxy quality in this run.
- mid remains the default bulk tradable bucket.
- low captures weaker/fragile edge cases.

Caveat:
- high bucket sample size is small; confirm over another larger window before locking permanently.

---

## Stability check

Post-change schema validity remained intact:
- reasons<2: 0
- risks<1: 0
- missing invalidation on trade actions: 0
- confidence out of range: 0
