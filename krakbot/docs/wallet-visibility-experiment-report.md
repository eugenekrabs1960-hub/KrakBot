# Wallet Visibility Experiment (Read-Only to Local Analyst)

Date: 2026-03-19  
Branch: `main`

Scope constraints respected:
- wallet visibility only (no score integration)
- no policy/gate changes
- no execution changes
- no live-default changes
- no news/social signals

## Exact prompt/packet visibility change made

File changed:
- `backend/app/services/models/qwen_local_adapter.py`

Change:
- local analyst now explicitly reads `packet.optional_signals.wallet_summary` **when present**.
- wallet fields are now included in analyst reasoning context:
  - `net_flow_bias`
  - `wallet_conviction_score`
  - `wallet_agreement_score`
  - `wallet_chasing_risk`
- added optional reason label: `wallet_flow_context`
- added wallet evidence paths to `evidence_used`
- wallet context added to thesis text for transparency

Read-only influence:
- only a small contextual adjustment to analyst **confidence semantics** based on wallet alignment/opposition and chasing risk.
- no changes to scoring engine, policy checks, or execution routing.

## Comparison window sizes

Both windows used 500 recent decisions after controlled paper runs.

- **Before visibility change**: 500 rows (`/tmp/wallet_vis_before.json`)
- **After visibility change**: 500 rows (`/tmp/wallet_vis_after.json`)

## Before/after action distribution

### Before
- long: 188
- short: 202
- no_trade: 110

### After
- long: 199
- short: 195
- no_trade: 106

Read:
- directional balance stayed stable.
- no_trade slightly decreased.

## Before/after setup_type distribution

### Before
- mean_reversion: 385
- trend_continuation: 4
- breakout_confirmation: 1
- unclear: 110

### After
- mean_reversion: 389
- trend_continuation: 5
- breakout_confirmation: 0
- unclear: 106

Read:
- setup identity remained essentially unchanged.

## Before/after allowed-trade quality

### Before
- allow-trade count: 46
- 15m quality: 34.78%
- 1h quality: 45.65%

### After
- allow-trade count: 78
- 15m quality: 41.03%
- 1h quality: 48.72%

Read:
- allowed-trade quality improved modestly while throughput rose.

## Before/after quality when wallet_summary is present vs absent

### Before
- wallet present:
  - count: 371
  - 15m: 40.93%
  - 1h: 47.67%
- wallet absent:
  - count: 19
  - 15m: 31.58%
  - 1h: 47.37%

### After
- wallet present:
  - count: 394
  - 15m: 40.93%
  - 1h: 49.18%
- wallet absent:
  - count: 0

Read:
- post window had effectively full wallet coverage for trade-action packets, so present-vs-absent comparison is no longer symmetric.
- within available evidence, wallet-visible context did not degrade quality and appears mildly helpful at 1h.

## Stability checks

Post-change schema validity remained clean:
- invalid reasons<2: 0
- invalid risks<1: 0
- missing invalidation on trade actions: 0

## Recommendation

**Keep wallet visibility enabled** as optional analyst context.

Why:
- no adverse impact observed on decision quality in this controlled run
- modest improvement in allowed-trade quality
- strategy identity remained stable

Caveat:
- because post window had near-total wallet presence, run one additional confirmation window for robustness before attributing gains solely to wallet visibility.
