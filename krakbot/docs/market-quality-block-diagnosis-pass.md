# Market-Quality Block Diagnosis Pass (Narrow)

Date: 2026-03-18/19  
Branch: `main`  
Scope: diagnosis only; no threshold changes in this pass.

## Goals covered
1. Break down `block_market_conditions` into exact failing sub-checks ✅
2. Measure frequency of each sub-check in controlled paper window ✅
3. Determine dominant checks ✅
4. Keep live defaults untouched ✅
5. No new product features ✅
6. Only tune if evidence clearly shows overblocking ✅

---

## Controlled validation window

Setup:
- mode: `paper`
- `live_armed=false`
- decision loop interval temporarily set to 3600s to reduce background noise during window
- ran 30 manual cycles (~90 policy rows analyzed)

Window summary:
- policy rows: 90
- market-quality blocks: 30
- market block rate: 33.3%

---

## Sub-cause breakdown of `block_market_conditions`

From policy reason tags + gate flags:

### Failure frequency by sub-check
- `freshness_check_failed`: **21**
- `liquidity_check_failed`: **10**
- `volatility_check_failed`: **3**

### Co-failure patterns
- only freshness: **17**
- only liquidity: **7**
- only volatility: **2**
- freshness + liquidity: **3**
- freshness + volatility: **1**
- liquidity + volatility: **0**
- all three: **0**

### Dominance conclusion
- **Freshness** is the dominant market-quality blocker.
- Liquidity is secondary.
- Volatility contributes minimally.

---

## Are market-quality blocks likely over-strict?

Counterfactual proxy check on blocked market-quality trade intents:
- would-have-worked @15m proxy: **39.3%** (11/28)
- would-have-worked @1h proxy: **44.4%** (8/18)

Interpretation:
- blocked candidates underperform a 50% directional baseline in this sample.
- evidence does **not** clearly indicate severe overblocking at market-quality layer.

Verdict:
- current market-quality filtering appears **mostly appropriate**, with possible mild strictness concentrated in freshness.

---

## Threshold adjustment decision in this pass

- **No threshold changes made** in this diagnosis pass.
- therefore no before/after post-adjustment section is included here.

If a future narrow adjustment is requested, the most evidence-supported first candidate is a very small paper-only freshness relaxation (single-rule test), then immediate re-validation.

---

## Final recommendation

- Keep current market-quality thresholds unchanged for now.
- Monitor freshness-driven blocks across another larger paper window.
- If tuning next, change only one rule first (freshness), and re-check:
  - trade-through
  - blocked-trade counterfactual quality
  - output validity/coherence
