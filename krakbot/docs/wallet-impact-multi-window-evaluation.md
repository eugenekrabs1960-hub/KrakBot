# Wallet-Impact Multi-Window Evaluation (Aggregated)

Date: 2026-03-19  
Branch: `main`  
Scope: analysis only. No prompt/threshold/scoring/live-default changes in this phase.

## Objective
Compare **baseline (no wallet visibility)** vs **wallet-visible** behavior across multiple windows and evaluate whether wallet visibility is helpful, neutral, or harmful.

## Window sets

### Baseline (no-wallet-visibility) windows
- `/tmp/confirm_large.json`
- `/tmp/high_before.json`
- `/tmp/identity_confirm.json`

### Wallet-visible windows
- `/tmp/wallet_vis_after.json`
- `/tmp/wallet_confirm.json`
- `/tmp/identity_after.json`

Each window uses 500-row slices from recent decisions.

---

## Aggregated action distribution (mean ± std as share of rows)

### Baseline
- long: **0.4000 ± 0.0065**
- short: **0.3887 ± 0.0052**
- no_trade: **0.2113 ± 0.0077**

### Wallet-visible
- long: **0.3847 ± 0.0100**
- short: **0.4167 ± 0.0191**
- no_trade: **0.1987 ± 0.0115**

Read:
- no_trade modestly lower with wallet visibility.
- slight shift from long toward short in wallet-visible runs.

---

## Aggregated setup_type distribution (mean ± std)

### Baseline
- mean_reversion: **0.6853 ± 0.0671**
- trend_continuation: **0.0933 ± 0.0589**
- breakout_confirmation: **0.0100 ± 0.0028**
- unclear: **0.2113 ± 0.0077**

### Wallet-visible
- mean_reversion: **0.7620 ± 0.0346**
- trend_continuation: **0.0353 ± 0.0431**
- breakout_confirmation: **0.0040 ± 0.0028**
- unclear: **0.1987 ± 0.0115**

Read:
- wallet-visible regime is more strongly mean-reversion-first with less trend/breakout usage.

---

## Aggregated gate distribution (mean ± std)

### Baseline
- allow_trade: **0.0613 ± 0.0195**
- downgrade_to_watch: **0.2113 ± 0.0077**
- block_market_conditions: **0.3867 ± 0.0146**
- block_risk: **0.3407 ± 0.0344**

### Wallet-visible
- allow_trade: **0.1020 ± 0.0530**
- downgrade_to_watch: **0.1987 ± 0.0115**
- block_market_conditions: **0.3887 ± 0.0109**
- block_risk: **0.3107 ± 0.0460**

Read:
- wallet-visible runs show higher average throughput (allow rate), but variance is high.

---

## Allowed-trade quality (aggregated)

### Baseline
- 15m accuracy: **0.4707 ± 0.0117**
- 1h accuracy: **0.5270 ± 0.0821**
- side-adjusted avg move 15m: **+1.84e-05 ± 2.49e-05**
- side-adjusted avg move 1h: **-1.74e-05 ± 8.93e-05**
- mean allowed count/window: **30.7 ± 9.7**

### Wallet-visible
- 15m accuracy: **0.4423 ± 0.1045**
- 1h accuracy: **0.4624 ± 0.0969**
- side-adjusted avg move 15m: **-2.95e-06 ± 3.24e-05**
- side-adjusted avg move 1h: **-2.25e-06 ± 7.01e-05**
- mean allowed count/window: **51.0 ± 26.5**

Read:
- allowed throughput is higher in wallet-visible runs,
- but allowed-quality is lower on average and much noisier.

---

## Overall trade-action quality (aggregated)

### Baseline
- 15m accuracy: **0.4777 ± 0.0115**
- 1h accuracy: **0.5127 ± 0.0033**
- side-adjusted avg move 15m: **+5.77e-06 ± 2.00e-05**
- side-adjusted avg move 1h: **+5.33e-05 ± 6.19e-05**

### Wallet-visible
- 15m accuracy: **0.4271 ± 0.0241**
- 1h accuracy: **0.4875 ± 0.0389**
- side-adjusted avg move 15m: **-1.07e-05 ± 1.97e-05**
- side-adjusted avg move 1h: **+4.03e-05 ± 5.83e-05**

Read:
- overall trade-action quality is weaker in wallet-visible aggregate.

---

## Variance summary

Wallet-visible windows show substantially higher variance in:
- allow rate
- allowed-trade quality
- overall 1h quality

This weakens confidence that wallet visibility is consistently beneficial right now.

---

## Verdict: helpful / neutral / harmful?

**Current verdict: neutral-to-harmful (inconclusive with downside skew).**

Why:
- some individual wallet-visible windows improved throughput/quality,
- but aggregated multi-window results show lower average quality and higher variance vs baseline.

---

## Recommendation

Do **not** remove wallet visibility outright (it remains useful context), but do **not** treat current wallet-visible behavior as quality-improving baseline yet.

Practical stance:
1. keep wallet visibility behind a controllable analyst-context toggle,
2. continue collecting multi-window evidence,
3. avoid granting wallet context stronger influence until stability improves.
