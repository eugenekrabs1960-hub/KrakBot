# Paper-Only Freshness Experiment Report (Very Narrow)

Date: 2026-03-18/19  
Branch: `main`  
Scope: one-rule paper freshness experiment only. No liquidity/volatility changes. No live setting changes.

## Experiment design

- Baseline controlled paper window (~90 policy rows): `fresh_before.json`
- Temporary experiment: paper-only freshness check loosened by **0.03**
  - effective paper threshold: `min_freshness_score - 0.03`
- Post controlled paper window (~90 policy rows): `fresh_after.json`
- Live defaults remained unchanged and disarmed.

> After evaluation, the temporary relaxation was **not kept** (reverted).

---

## Required before/after metrics

### Baseline (before)
- allow_trade: **21**
- downgrade_to_watch: **19**
- block_market_conditions: **34**
- freshness_check_failed: **24**
- trade-through rate: **29.58%** (21/71)

### Experiment (after temporary freshness relaxation)
- allow_trade: **37**
- downgrade_to_watch: **22**
- block_market_conditions: **31**
- freshness_check_failed: **15**
- trade-through rate: **54.41%** (37/68)

Observed effect:
- Throughput increased sharply (not modest).
- Freshness-driven market blocks dropped materially.

---

## Proxy outcome quality of newly admitted trades

Approximation for newly admitted group:
- post-window allowed trades with freshness in `[0.27, 0.30)` (zone only admitted by relaxation)
- count: **5**

Proxy directional quality:
- 15m proxy: **0%** (0/5)
- 1h proxy: **33.3%** (1/3 with available horizon)

Interpretation:
- The newly admitted marginal freshness trades looked weak in this sample.

---

## Blocked-vs-allowed quality sanity check

Window-level proxy (directional):

### Before
- allowed: 15m **23.8%**, 1h **38.1%**
- blocked_market: 15m **26.7%**, 1h **45.0%**

### After
- allowed: 15m **24.2%**, 1h **50.0%**
- blocked_market: 15m **10.3%**, 1h **31.3%**

Reading:
- post window separates allowed vs blocked better at aggregate level,
- but **marginal newly admitted freshness-edge trades** underperformed.

---

## Conclusion

Success condition asked for a **modest** throughput increase without clear degradation.

Result:
- increase was **large**, not modest,
- newly admitted freshness-edge trades showed **clear quality degradation**.

Therefore this paper-only relaxation is **not accepted as stable**.

---

## Recommendation

- Keep current freshness threshold unchanged for now (baseline behavior).
- If re-testing freshness, do a smaller step (e.g. -0.01) with stricter acceptance criteria on newly admitted trade quality.
- Keep live-mode defaults/safeguards exactly as-is.
