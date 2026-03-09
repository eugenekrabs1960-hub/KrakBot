-- Phase 4: reliability hardening primitives

CREATE TABLE IF NOT EXISTS idempotency_keys (
  key TEXT PRIMARY KEY,
  scope TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  response JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reconciliations (
  id BIGSERIAL PRIMARY KEY,
  strategy_instance_id TEXT,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  details JSONB NOT NULL,
  ts BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reconciliations_sid_ts
  ON reconciliations(strategy_instance_id, ts DESC);

CREATE TABLE IF NOT EXISTS worker_checkpoints (
  worker_name TEXT PRIMARY KEY,
  checkpoint JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
