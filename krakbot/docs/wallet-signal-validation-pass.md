# Wallet-Signal Validation Pass (Read-Only)

Date: 2026-03-19  
Branch: `main`  
Scope: validation only. No scoring/policy/execution impact changes.

## Constraints respected
- wallet signals remained read-only
- no live default changes
- no news/social additions
- no decision impact introduced

## 1) Coverage report by tracked coin

From 500 recent packets:

- BTC:
  - total packets: 167
  - wallet_summary present: 88
  - wallet_summary null: 79
  - present rate: 52.69%
- ETH:
  - total packets: 167
  - wallet_summary present: 88
  - wallet_summary null: 79
  - present rate: 52.69%
- SOL:
  - total packets: 166
  - wallet_summary present: 88
  - wallet_summary null: 78
  - present rate: 53.01%

Interpretation:
- Coverage is roughly half-present/half-null in this window due sequencing/timing of summary creation vs packet retention window.
- Presence is balanced across tracked coins (no obvious coin-specific starvation).

## 2) Null / non-null rates

Global across tracked packets:
- non-null rate ~53%
- null rate ~47%

## 3) Distribution of wallet fields

### net_flow_bias (global)
- bullish: 102
- bearish: 81
- neutral: 81

### wallet_conviction_score (global)
- count: 264
- min: 0.0305
- p25: 0.0305
- p50: 0.1111
- p75: 0.5864
- max: 0.5864
- mean: 0.2435

### wallet_agreement_score (global)
- count: 264
- min: 0.5153
- p25: 0.5153
- p50: 0.5556
- p75: 0.7932
- max: 0.7932
- mean: 0.6218

### wallet_chasing_risk (global)
- count: 264
- min/p25/p50/p75/max: 0.0
- mean: 0.0

Interpretation:
- Bias and conviction vary by coin/time and are non-constant.
- Agreement also varies.
- Chasing risk currently lacks variance (always 0), indicating weak signal utility in current normalization.

## 4) Summary text quality examples

Examples observed:
- `ETH: bearish wallet flow, conviction=0.59, agreement=0.79, chasing_risk=0.00`
- `ETH: bullish wallet flow, conviction=0.39, agreement=0.69, chasing_risk=0.00`
- `SOL: bullish wallet flow, conviction=0.11, agreement=0.56, chasing_risk=0.00`
- `BTC: neutral wallet flow, conviction=0.03, agreement=0.52, chasing_risk=0.00`

Quality assessment:
- concise, structured, and readable
- non-generic enough for operator context
- still somewhat repetitive in format (acceptable for v1 telemetry)

## 5) Stability + meaningfulness recommendation

Is `wallet_summary` stable enough to expose to the local model as optional signal?

**Recommendation: yes, with caveats.**

Why yes:
- consistent presence across tracked coins
- key fields (bias/conviction/agreement) vary meaningfully by coin/time
- summary text is structured and interpretable

Caveats before decision-impact usage:
1. improve wallet_summary coverage toward higher non-null rate
2. increase `wallet_chasing_risk` sensitivity (currently near-constant zero)
3. verify cross-window stability over additional larger runs

Given current state, it is suitable as an **optional contextual field** for model consumption, but not yet mature for direct deterministic gating weight.
