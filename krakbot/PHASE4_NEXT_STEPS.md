# Krakbot Phase 4 Status (Reliability Hardening)

## Implemented

- Idempotency keys table + service (`idempotency_keys`, `services/idempotency.py`).
- `POST /api/trades/paper-order` now requires `x-idempotency-key` and safely replays duplicate requests.
- Reconciliation logs + APIs (`reconciliations`, `routes/reliability.py`).
- Worker checkpoint table + checkpoint helpers (`worker_checkpoints`, `services/checkpoints.py`).
- Kraken ingestor now stores/reloads checkpoint metadata for restart diagnostics.
- Added Phase 4 migration (`0004_reliability.sql`).
- Added initial backend test scaffolding for core service behavior.

## Reliability APIs

- `POST /api/reliability/reconcile/all`
- `POST /api/reliability/reconcile/{strategy_instance_id}`
- `GET /api/reliability/reconciliations?limit=50`

## Next hardening targets

1. Add stronger reconciliation rules (engine-vs-canonical order/fill parity checks).
2. Add dead-letter event handling for persistence failures.
3. Add retry policy with bounded jitter for external engine calls.
4. Add end-to-end tests in docker-compose CI flow.
