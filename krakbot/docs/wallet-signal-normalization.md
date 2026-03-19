# Wallet Signal Normalization (Read-Only v1)

This phase adds a **wallet-intelligence read-only signal layer** scoped to tracked coins only.

## Scope and guardrails

- Coverage is limited to `tracked_universe` coins.
- Wallet data is read-only and informational.
- Wallet signals are surfaced in UI and attached to FeaturePacket.
- Wallet signals **do not** affect scoring, policy, sizing, or execution in v1.
- No live-default changes.

## Data path

1. `run_decision_cycle()` iterates tracked coins.
2. For each coin:
   - ingest wallet events (`wallet_events`)
   - generate normalized wallet summary (`wallet_summaries`)
3. Latest summary is attached to `FeaturePacket.optional_signals.wallet_summary`.
4. Wallet summaries are exposed via API and overview UI panel.

## Storage tables

Migration: `backend/app/db/migrations/0019_wallet_signal_pipeline.sql`

- `wallet_events`
  - raw normalized event rows for tracked coins
  - includes: coin, symbol, wallet_address, side, notional_usd, event_ts, source, payload

- `wallet_summaries`
  - per-coin normalized summary snapshots
  - includes: generated_at + summary payload

## Normalized wallet summary fields

`wallet_summary` payload includes:

- `net_flow_bias` (`bullish|bearish|neutral`)
- `wallet_conviction_score` (0..1)
- `wallet_agreement_score` (0..1)
- `wallet_chasing_risk` (0..1)
- `summary_text` (human-readable compact explanation)
- `event_count`

## Current normalization logic

Implemented in `backend/app/services/wallet_signals.py`:

- `wallet_conviction_score` = `abs(net_flow) / total_flow`
- `wallet_agreement_score` = `max(buy_flow, sell_flow) / total_flow`
- `wallet_chasing_risk` = recent-flow intensity vs older baseline
- `net_flow_bias` from net-flow thresholding

## APIs

- `GET /api/wallets/summary` — latest summaries for tracked universe
- `GET /api/wallets/events` — recent wallet events (tracked universe)

## UI surface

Overview page includes **Wallet Intelligence (Read-Only)** panel.

## Explicit non-impact statement

Wallet signals are not used in:

- `compute_ml_scores`
- policy gate checks
- broker routing/execution

This keeps the phase purely additive and observational.
