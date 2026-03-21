CREATE TABLE IF NOT EXISTS autonomy_runs (
  run_id VARCHAR(64) PRIMARY KEY,
  started_at TIMESTAMP NOT NULL,
  finished_at TIMESTAMP NULL,
  status VARCHAR(32) NOT NULL,
  phase VARCHAR(32) NOT NULL,
  trigger VARCHAR(32) NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_autonomy_runs_started_at ON autonomy_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_autonomy_runs_status ON autonomy_runs(status);

CREATE TABLE IF NOT EXISTS autonomy_hypotheses (
  hypothesis_id VARCHAR(64) PRIMARY KEY,
  created_at TIMESTAMP NOT NULL,
  status VARCHAR(32) NOT NULL,
  weak_spot VARCHAR(128) NOT NULL,
  rationale TEXT NOT NULL,
  change_path VARCHAR(128) NOT NULL,
  change_value TEXT NOT NULL,
  source_run_id VARCHAR(64) NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_autonomy_hypotheses_created_at ON autonomy_hypotheses(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_autonomy_hypotheses_status ON autonomy_hypotheses(status);

CREATE TABLE IF NOT EXISTS autonomy_promotions (
  promotion_id VARCHAR(64) PRIMARY KEY,
  created_at TIMESTAMP NOT NULL,
  status VARCHAR(32) NOT NULL,
  hypothesis_id VARCHAR(64) NOT NULL REFERENCES autonomy_hypotheses(hypothesis_id),
  target_mode VARCHAR(32) NOT NULL,
  target_scope VARCHAR(32) NOT NULL,
  pre_snapshot_id VARCHAR(64) NOT NULL,
  post_snapshot_id VARCHAR(64) NULL,
  reason TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_autonomy_promotions_created_at ON autonomy_promotions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_autonomy_promotions_status ON autonomy_promotions(status);

CREATE TABLE IF NOT EXISTS runtime_config_snapshots (
  snapshot_id VARCHAR(64) PRIMARY KEY,
  created_at TIMESTAMP NOT NULL,
  source VARCHAR(32) NOT NULL,
  mode VARCHAR(32) NOT NULL,
  settings_json JSONB NOT NULL,
  hash VARCHAR(128) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runtime_snapshots_created_at ON runtime_config_snapshots(created_at DESC);

CREATE TABLE IF NOT EXISTS autonomy_rollbacks (
  rollback_id VARCHAR(64) PRIMARY KEY,
  created_at TIMESTAMP NOT NULL,
  status VARCHAR(32) NOT NULL,
  promotion_id VARCHAR(64) NOT NULL REFERENCES autonomy_promotions(promotion_id),
  from_snapshot_id VARCHAR(64) NOT NULL,
  to_snapshot_id VARCHAR(64) NOT NULL,
  trigger_reason VARCHAR(128) NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_autonomy_rollbacks_created_at ON autonomy_rollbacks(created_at DESC);

CREATE TABLE IF NOT EXISTS autonomy_events (
  event_id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMP NOT NULL,
  run_id VARCHAR(64) NULL,
  entity_type VARCHAR(32) NOT NULL,
  entity_id VARCHAR(64) NOT NULL,
  event_type VARCHAR(64) NOT NULL,
  severity VARCHAR(16) NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_autonomy_events_ts ON autonomy_events(ts DESC);
CREATE INDEX IF NOT EXISTS idx_autonomy_events_entity ON autonomy_events(entity_type, entity_id);
