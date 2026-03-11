CREATE TABLE IF NOT EXISTS wallet_pipeline_run_ledger (
  run_id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at_ms BIGINT NOT NULL,
  heartbeat_at_ms BIGINT NOT NULL,
  finished_at_ms BIGINT,
  duration_ms BIGINT,
  error_text TEXT,
  result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_wallet_pipeline_run_ledger_started ON wallet_pipeline_run_ledger(started_at_ms DESC);

CREATE TABLE IF NOT EXISTS wallet_pipeline_lock (
  lock_name TEXT PRIMARY KEY,
  owner_run_id TEXT,
  acquired_at_ms BIGINT,
  heartbeat_at_ms BIGINT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO wallet_pipeline_lock(lock_name, owner_run_id, acquired_at_ms, heartbeat_at_ms)
VALUES ('wallet_pipeline', NULL, NULL, NULL)
ON CONFLICT (lock_name) DO NOTHING;
