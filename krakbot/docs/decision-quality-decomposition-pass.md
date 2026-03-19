# Decision-Quality Decomposition Pass (No-Tuning)

Date: 2026-03-19  
Branch: `main`  
Scope: analysis only. No tuning/model/threshold/live-default changes.

## Window
- 500 recent decision rows (paper mode)
- Source: `/tmp/confirm_large.json`

---

## 1) Quality breakdown by setup_type

(Trade actions only, directional proxy quality)

- **mean_reversion** (n=322)
  - 15m accuracy: **48.7%**
  - 1h accuracy: **52.5%**
- **trend_continuation** (n=68)
  - 15m accuracy: **51.5%**
  - 1h accuracy: **45.3%**
- **breakout_confirmation** (n=6)
  - 15m accuracy: **40.0%**
  - 1h accuracy: **60.0%** *(tiny n)*

Read:
- Most reliable broad style in this sample is **mean_reversion** (best 1h stability at useful sample size).
- Trend continuation appears okay short horizon, weaker at 1h.
- Breakout is too sparse to be a primary identity signal yet.

---

## 2) Quality breakdown by side (long vs short)

- **long** (n=204)
  - 15m accuracy: **51.7%**
  - 1h accuracy: **51.3%**
- **short** (n=192)
  - 15m accuracy: **46.3%**
  - 1h accuracy: **51.4%**

Read:
- At 1h, long/short are essentially symmetric.
- At 15m, long is somewhat stronger.
- No strong evidence to hard-bias one direction overall.

---

## 3) Quality breakdown by gate result

For trade-intent rows (`requested_action in {long, short}`):

- **allow_trade** (n=21)
  - 15m accuracy: **47.6%**
  - 1h accuracy: **42.9%**
- **block_market_conditions** (n=199)
  - 15m accuracy: **49.7%**
  - 1h accuracy: **54.9%**
- **block_risk** (n=176)
  - 15m accuracy: **48.6%**
  - 1h accuracy: **48.5%**

For downgraded no-trade rows (`downgrade_to_watch`, requested no_trade):
- count: 104
- no-trade correctness proxy:
  - 15m: **63.7%**
  - 1h: **31.3%**

Read:
- Allowed trades are not currently outperforming blocked trade-intents in this sample.
- This points to decision-quality/selectivity mismatch vs gate routing, not just gate tightness.

---

## 4) Key reasoning pattern decomposition

Top trade-action reasoning patterns:

1. `[momentum_alignment, execution_quality, trend_quality]`
   - count: 390
   - 15m: 49.2%
   - 1h: 51.2%

2. `[momentum_alignment, execution_quality, validated_breakout]`
   - count: 6
   - 15m: 40.0%
   - 1h: 60.0% *(tiny n)*

Read:
- Reasoning is dominated by one template.
- Little diversification across reasoning motifs; weak interpretability for style-specific performance.

---

## 5) Strategy identity recommendation (emphasize/suppress next)

### Emphasize next
1. **Mean reversion as core identity**
   - strongest broad 1h behavior at meaningful sample size.
2. **Neutral directional stance at 1h**
   - keep both long/short active; avoid hard directional bias.

### Suppress/de-emphasize next
1. **Trend continuation at 1h until quality improves**
   - currently underperforming mean reversion on 1h.
2. **Breakout as primary style**
   - keep strict/rare until larger-sample evidence appears.

---

## Practical implication
Current bot identity should be:
- **mean-reversion-first, risk-disciplined, breakout-selective**,
- with trend continuation treated as secondary and quality-monitored.

No changes applied in this pass.
