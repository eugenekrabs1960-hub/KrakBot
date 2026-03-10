# Wallet Intelligence Benchmark (WIB) — Handoff Spec (MVP v1)

## Goal
Add a provider-agnostic Wallet Intelligence Benchmark subsystem to KrakBot that:
- ranks wallets from inferred high-confidence SOL-directional trade-like events
- builds a stable cohort benchmark
- exposes benchmark signals for operator analysis and KrakBot-vs-benchmark alignment

This is **benchmark intelligence first** (not copy-trading).

## Scope (v1)
- Solana-first operational flow
- SOL-only scoring relevance
- Provider-agnostic adapter interface
- Rule-based explainable inference/classification/scoring
- Approximate benchmark performance model (not tax-lot perfect accounting)

## Out-of-scope (v1)
- Auto-copy execution
- Multi-chain ranking parity
- ML-driven ranking core
- Perfect on-chain wallet accounting truth

---

## Architecture

1. Provider Adapters
   - Pull wallet activity from provider APIs
   - Persist raw payloads + cursors
2. Normalization + Inference
   - Normalize provider payloads to canonical events
   - Infer directional trade-like events with confidence tiers (T1/T2/T3)
3. Classification + Eligibility
   - Label wallet types, exclude infra/plumbing wallets
   - Apply eligibility gates for scoring inclusion
4. Scoring + Cohort
   - Compute rolling scores (7/30/90d)
   - Build stable cohort with anti-churn hysteresis
5. Benchmark Signals
   - Emit bias, strength, confidence, breadth, concentration, activity
6. KrakBot Alignment
   - Tag trade/strategy/platform alignment vs benchmark state

---

## Canonical entities (v1)
- `wallet_master`
- `wallet_provider_identity`
- `wallet_raw_event`
- `wallet_canonical_event`
- `wallet_inferred_event`
- `wallet_classification`
- `wallet_eligibility_snapshot`
- `wallet_score_snapshot`
- `wallet_cohort_definition`
- `wallet_cohort_membership`
- `wallet_cohort_snapshot`
- `wallet_benchmark_signal`
- `strategy_benchmark_alignment`

All derived entities must include:
- `logic_version`
- `config_hash`
- `generated_at`
- `run_id`

---

## Classification/exclusion rules (v1)
Classes:
- `smart_money_candidate`, `active_speculator`, `discretionary_trader`,
- `infra_exchange`, `market_maker_like`, `bot_like`, `inactive`, `unknown`

Hard excludes from ranking:
- exchange/bridge/router/treasury/protocol plumbing style wallets

Soft excludes/penalties:
- market-maker-like, bot-like (configurable)

Manual controls:
- force include, force exclude, label lock

---

## Inference model (v1)
Confidence tiers:
- T1 = high confidence (primary ranking input)
- T2 = medium confidence (context only)
- T3 = low confidence (debug/research only)

T1 requirements (SOL-only):
- clear SOL exposure-change direction
- coherent event sequence semantics
- sufficient notional significance
- low ambiguity flags

Not counted as score-driving in v1:
- pure transfers/self-shuffles
- bridge-only movement without directional trade signal
- rewards/airdrops/staking-only movements
- micro-notional/noisy flows

---

## Eligibility gates (MVP defaults)
30d lookback default:
- T1 count >= 20
- active days >= 10
- recency: >=1 T1 event in last 5d
- SOL relevance >= 80%
- cumulative T1 notional >= $25,000
- not hard-excluded class
- data quality/freshness checks pass

---

## Scoring model (MVP)
Windows:
- 7d (short-term), 30d (primary), 90d (stability)

Components:
- performance
- consistency
- reliability
- asset_relevance
- conviction
- stability
- penalties

Blend recommendation:
- 30d 55% + 7d 25% + 90d 20%

Anti-spike controls:
- max rank jump clamp
- sparse-wallet cap/penalty
- confidence weighting

---

## Performance/benchmark math (approximate)
Per-event quality:
- markout horizons: 15m, 1h, 4h, 24h
- side-aware quality scoring (buy-like vs sell-like)

Wallet performance blend:
- event markout quality (core)
- exposure-change quality
- approximate realized event-return quality (when confidence strong)

Benchmark outputs:
- valid/high-confidence: bias, breadth, confidence, activity
- approximate: ROI/equity/PnL curves

All approximate outputs must be clearly labeled in API/UI.

---

## Cohort model
Primary cohort (v1): `top_sol_active_wallets`

- target size: 50 (configurable 30–75)
- refresh score cadence: 6h
- refresh membership cadence: 24h
- hysteresis: retain existing member down to rank N+buffer
- minimum tenure: 3d unless hard disqualify

---

## Benchmark signal API contract (v1)
Primary outputs:
- `bias_state` (bullish/bearish/neutral)
- `bias_strength` (0-100)
- `benchmark_confidence` (0-100)
- `breadth_score`
- `concentration_score`
- `active_wallet_count`
- `cohort_markout_quality_rolling`
- `benchmark_equity_index_approx`

Low confidence behavior:
- expose `insufficient_benchmark_confidence`
- downstream aligners degrade to neutral/insufficient

---

## KrakBot alignment model
Tags:
- `aligned_bullish`, `aligned_bearish`
- `opposed_bullish`, `opposed_bearish`
- `neutral`
- `insufficient_benchmark_confidence`

Store at trade/strategy/platform granularity with benchmark context snapshot IDs.

---

## Failure/trust model
Degraded states:
- `PROVIDER_STALE`
- `INFERENCE_DEGRADED`
- `COHORT_THIN`
- `LOW_CONFIDENCE`
- `PARTIAL_COVERAGE`

Behavior:
- freeze membership updates on severe staleness
- continue last-known signal but mark stale
- force downstream to insufficient-confidence below threshold

---

## Versioning
Independent versions:
- inference rules
- classification logic
- eligibility profile
- score formula
- cohort construction logic

Never rewrite historical snapshots; write new versioned snapshots.

---

## Rollout phases
1. Shadow ingest (raw+canonical only)
2. Shadow scoring diagnostics
3. Operator-facing benchmark UI/API
4. EIF alignment tags (advisory)
5. Optional strategy consumption behind feature flags

---

## Implementation notes for agent
- Keep provider adapters isolated from ranking logic
- Use immutable raw event storage
- Use only T1 for primary ranking in v1
- SOL-only score scope for v1
- Treat ROI/equity as approximation, not accounting truth
- Prefer explicit reason codes and explainability fields everywhere
