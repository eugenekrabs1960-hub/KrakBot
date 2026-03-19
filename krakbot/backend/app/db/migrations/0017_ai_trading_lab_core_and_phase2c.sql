-- KrakBot AI Trading Lab core tables + phase 2c observability tables

CREATE TABLE IF NOT EXISTS feature_packets (
  packet_id VARCHAR(64) PRIMARY KEY,
  coin VARCHAR(32) NOT NULL,
  symbol VARCHAR(64) NOT NULL,
  generated_at TIMESTAMP NOT NULL,
  payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feature_packets_coin ON feature_packets (coin);
CREATE INDEX IF NOT EXISTS idx_feature_packets_symbol ON feature_packets (symbol);
CREATE INDEX IF NOT EXISTS idx_feature_packets_generated_at ON feature_packets (generated_at DESC);

CREATE TABLE IF NOT EXISTS decision_outputs (
  id BIGSERIAL PRIMARY KEY,
  packet_id VARCHAR(64) NOT NULL,
  action VARCHAR(32) NOT NULL,
  confidence DOUBLE PRECISION NOT NULL,
  generated_at TIMESTAMP NOT NULL,
  payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_decision_outputs_packet_id ON decision_outputs (packet_id);
CREATE INDEX IF NOT EXISTS idx_decision_outputs_generated_at ON decision_outputs (generated_at DESC);

CREATE TABLE IF NOT EXISTS policy_decisions (
  policy_decision_id VARCHAR(64) PRIMARY KEY,
  packet_id VARCHAR(64) NOT NULL,
  final_action VARCHAR(64) NOT NULL,
  evaluated_at TIMESTAMP NOT NULL,
  payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_policy_decisions_packet_id ON policy_decisions (packet_id);
CREATE INDEX IF NOT EXISTS idx_policy_decisions_evaluated_at ON policy_decisions (evaluated_at DESC);

CREATE TABLE IF NOT EXISTS execution_records (
  execution_id VARCHAR(64) PRIMARY KEY,
  packet_id VARCHAR(64) NOT NULL,
  symbol VARCHAR(64) NOT NULL,
  action VARCHAR(32) NOT NULL,
  mode VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL,
  fill_price DOUBLE PRECISION NULL,
  filled_notional_usd DOUBLE PRECISION NULL,
  created_at TIMESTAMP NOT NULL,
  payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_execution_records_packet_id ON execution_records (packet_id);
CREATE INDEX IF NOT EXISTS idx_execution_records_symbol ON execution_records (symbol);
CREATE INDEX IF NOT EXISTS idx_execution_records_created_at ON execution_records (created_at DESC);

CREATE TABLE IF NOT EXISTS positions (
  symbol VARCHAR(64) PRIMARY KEY,
  qty DOUBLE PRECISION NOT NULL DEFAULT 0,
  avg_entry DOUBLE PRECISION NOT NULL DEFAULT 0,
  mode VARCHAR(32) NOT NULL DEFAULT 'paper',
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS outcome_labels (
  outcome_id VARCHAR(64) PRIMARY KEY,
  packet_id VARCHAR(64) NOT NULL,
  payload JSONB NOT NULL,
  generated_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outcome_labels_packet_id ON outcome_labels (packet_id);
CREATE INDEX IF NOT EXISTS idx_outcome_labels_generated_at ON outcome_labels (generated_at DESC);

CREATE TABLE IF NOT EXISTS config_profiles (
  profile_id VARCHAR(128) PRIMARY KEY,
  profile_type VARCHAR(64) NOT NULL,
  version VARCHAR(64) NOT NULL,
  active BOOLEAN NOT NULL DEFAULT FALSE,
  payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_config_profiles_type ON config_profiles (profile_type);
CREATE INDEX IF NOT EXISTS idx_config_profiles_active ON config_profiles (active);

CREATE TABLE IF NOT EXISTS tracked_universe (
  coin VARCHAR(32) PRIMARY KEY,
  enabled BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS review_reports (
  review_id VARCHAR(64) PRIMARY KEY,
  packet_id VARCHAR(64) NOT NULL,
  recommendation VARCHAR(128) NOT NULL,
  payload JSONB NOT NULL,
  generated_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_review_reports_packet_id ON review_reports (packet_id);

-- phase 2c tables
CREATE TABLE IF NOT EXISTS loop_runs (
  run_id VARCHAR(64) PRIMARY KEY,
  loop_type VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL,
  started_at TIMESTAMP NOT NULL,
  finished_at TIMESTAMP NULL,
  duration_ms INTEGER NULL,
  message TEXT NULL
);
CREATE INDEX IF NOT EXISTS idx_loop_runs_type_started ON loop_runs (loop_type, started_at DESC);

CREATE TABLE IF NOT EXISTS live_relay_requests (
  idempotency_key VARCHAR(64) PRIMARY KEY,
  action VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload JSONB NOT NULL,
  response JSONB NOT NULL,
  created_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_live_relay_requests_action_created ON live_relay_requests (action, created_at DESC);

CREATE TABLE IF NOT EXISTS reconciliation_runs (
  recon_id VARCHAR(64) PRIMARY KEY,
  mode VARCHAR(32) NOT NULL,
  broker_position_count INTEGER NOT NULL,
  local_position_count INTEGER NOT NULL,
  drift_count INTEGER NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reconciliation_runs_created_at ON reconciliation_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reconciliation_runs_status ON reconciliation_runs (status);
