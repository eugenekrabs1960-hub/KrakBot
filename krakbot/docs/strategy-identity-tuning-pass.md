# Strategy-Identity Tuning Pass (Narrow)

Date: 2026-03-19  
Branch: `main`

Scope constraints respected:
- mean_reversion emphasis
- trend_continuation de-emphasis (especially 1h)
- breakout kept strict/rare
- no new data sources
- no live default or safety threshold changes

## Exact changes made

File changed:
- `backend/app/services/models/qwen_local_adapter.py`

### Setup-type preference logic updated

1. **Kept strict breakout discipline**
- `breakout_confirmation` remains only when `breakout_strong` is true.

2. **Made trend_continuation harder to assign**
- introduced stricter gate `trend_continuation_strong` requiring:
  - high momentum
  - high trend alignment + trend quality
  - low contradiction + low extension
  - adequate freshness + low fragility

3. **Mean reversion as default trade style**
- if trade action is not no_trade,
- and not `breakout_strong`,
- and not `trend_continuation_strong`,
- then setup_type = `mean_reversion`.

No confidence-band logic changed in this pass.
No threshold changes.

---

## Before/after setup_type distribution

### Before (500-row window)
- mean_reversion: **325**
- trend_continuation: **67**
- breakout_confirmation: **5**
- unclear: **103**

### After (500-row window)
- mean_reversion: **357**
- trend_continuation: **48**
- breakout_confirmation: **3**
- unclear: **92**

Read:
- strategy identity shifted in intended direction:
  - mean_reversion increased
  - trend_continuation reduced
  - breakout stayed strict/rare

---

## Before/after quality by setup_type

### Before
- mean_reversion:
  - 15m: 48.1% (n=318)
  - 1h: 51.8% (n=303)
- trend_continuation:
  - 15m: 44.6% (n=65)
  - 1h: 48.3% (n=60)
- breakout_confirmation:
  - 15m: 20.0% (n=5)
  - 1h: 40.0% (n=5)

### After
- mean_reversion:
  - 15m: 47.1% (n=348)
  - 1h: 54.5% (n=330)
- trend_continuation:
  - 15m: 41.7% (n=48)
  - 1h: 45.8% (n=48)
- breakout_confirmation:
  - 15m: 0.0% (n=3)
  - 1h: 33.3% (n=3)

Read:
- mean_reversion 1h quality improved.
- trend_continuation remains weaker than mean_reversion.
- breakout remains too small-sample to optimize around.

---

## Before/after allowed-trade quality

### Before
- allow_trade count: 15
- 15m quality: 53.3%
- 1h quality: 46.7%

### After
- allow_trade count: 60
- 15m quality: 58.3%
- 1h quality: 56.7%

Read:
- allowed-trade quality improved in this sample while strategy identity became clearer.

---

## Recommendation: strategy identity strength

Yes — the bot now has a clearer identity:
- **mean-reversion-first**,
- **trend-continuation-secondary**,
- **breakout-selective/rare**.

This identity is consistent with current decomposition findings and produced better 1h quality for the emphasized style in this run.

Suggested next step (if requested later):
- continue monitoring whether mean_reversion leadership persists over another large confirmation window before additional tuning.
