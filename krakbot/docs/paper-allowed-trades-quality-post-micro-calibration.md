# Paper Allowed-Trade Quality Validation (Post Portfolio-Limit Micro-Calibration)

Date: 2026-03-18/19  
Branch: `main`  
Scope: validation only (no threshold changes in this phase)

## Method

Compared two controlled paper-mode windows (each ~90 decisions):
- **Pre micro-calibration** window: `/tmp/micro_before.json`
- **Post micro-calibration** window: `/tmp/micro_after_v2.json`

Allowed trades were evaluated using short-horizon **proxy outcomes** derived from subsequent packet mark prices in the same symbol stream:
- 15m proxy = +3 packet steps
- 1h proxy = +12 packet steps

> Note: this is accelerated-cycle proxy evaluation, not wall-clock candle backtest.

---

## 1) Pre vs post allowed-trade quality

### Pre micro-calibration (allowed trades only)
- allowed_count: **4**
- directional accuracy (15m proxy): **25.0%** (1/4)
- directional accuracy (1h proxy): **100.0%** (4/4)
- side-adjusted avg move (15m proxy): **-0.0029%**
- side-adjusted avg move (1h proxy): **+0.0888%**

### Post micro-calibration (allowed trades only)
- allowed_count: **8**
- directional accuracy (15m proxy): **87.5%** (7/8)
- directional accuracy (1h proxy): **100.0%** (8/8)
- side-adjusted avg move (15m proxy): **+0.0265%**
- side-adjusted avg move (1h proxy): **+0.0430%**

### Readout
- Newly admitted throughput (4 -> 8 allowed in window) did **not** degrade short-horizon quality.
- Post window quality looked at least as sane as pre window, with better 15m hit-rate.

---

## 2) Sample of newly allowed trades (post window)

Sample (8 allowed trades):

| packet_id | symbol | side | 15m proxy | 15m dir ok | 1h proxy | 1h dir ok |
|---|---|---:|---:|:---:|---:|:---:|
| pkt_7ab72a3446db | SOL-PERP | short | -0.0288% | ✅ | -0.0455% | ✅ |
| pkt_3e7923df6f62 | BTC-PERP | long | +0.0226% | ✅ | +0.0184% | ✅ |
| pkt_f2b2751314b0 | SOL-PERP | short | -0.0089% | ✅ | -0.0810% | ✅ |
| pkt_e0c6c0d66dbb | BTC-PERP | short | -0.0438% | ✅ | -0.0395% | ✅ |
| pkt_b30411ba5696 | ETH-PERP | short | -0.0500% | ✅ | -0.0590% | ✅ |
| pkt_60111e5498ea | BTC-PERP | short | -0.0438% | ✅ | -0.0395% | ✅ |
| pkt_6e76e53d234a | ETH-PERP | short | -0.0273% | ✅ | -0.0500% | ✅ |
| pkt_1e11e1c26e96 | BTC-PERP | short | +0.0127% | ❌ | -0.0113% | ✅ |

Qualitative take:
- Trades look coherent (small-magnitude, directionally sensible for paper hypothesis testing).
- One near-term miss exists (healthy; not overfit-perfect).

---

## 3) Are market_quality blocks mostly justified?

Post window block diagnostics:
- `block_market_conditions`: **36**
- subreasons among those blocks:
  - `freshness_check_failed`: **28**
  - `liquidity_check_failed`: **9**
  - `volatility_check_failed`: **5**

Counterfactual quality check for blocked market-condition trades (requested long/short only):
- would-have-worked at 15m proxy: **54.3%** (19/35)
- would-have-worked at 1h proxy: **37.0%** (10/27)

Interpretation:
- 1h proxy suggests most market blocks are **likely justified**.
- 15m proxy is mixed, indicating some opportunity cost.
- Overall verdict: **mixed-to-mostly-correct**, with freshness as the dominant gate.

---

## 4) Recommendation (no threshold change in this phase)

Given this validation:
- Leave current thresholds unchanged **for now**.
- If tuning one market-quality rule next, target only **freshness** first (dominant blocker), with a very small paper-only relaxation and re-test.

Why freshness first:
- it drives most market-quality blocks
- it is the least structural risk compared with broad liquidity/volatility loosening
- can be tuned narrowly and measured quickly

---

## Conclusion

Post portfolio-limit micro-calibration, newly allowed paper trades appear sane and not lower-quality in this sample.  
`block_market_conditions` appears mixed-to-mostly justified, and the next likely over-strict bottleneck to test (if any) is **freshness**.
