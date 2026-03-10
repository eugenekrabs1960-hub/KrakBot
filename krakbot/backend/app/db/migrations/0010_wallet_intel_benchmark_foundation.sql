CREATE TABLE IF NOT EXISTS wallet_master (
  id TEXT PRIMARY KEY,
  chain TEXT NOT NULL,
  address TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  labels_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  manual_force_include BOOLEAN NOT NULL DEFAULT FALSE,
  manual_force_exclude BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(chain, address)
);

CREATE TABLE IF NOT EXISTS wallet_provider_identity (
  id BIGSERIAL PRIMARY KEY,
  wallet_id TEXT NOT NULL REFERENCES wallet_master(id),
  provider TEXT NOT NULL,
  provider_wallet_ref TEXT NOT NULL,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(provider, provider_wallet_ref)
);

CREATE TABLE IF NOT EXISTS wallet_raw_event (
  id TEXT PRIMARY KEY,
  wallet_id TEXT NOT NULL REFERENCES wallet_master(id),
  provider TEXT NOT NULL,
  provider_event_id TEXT,
  chain TEXT NOT NULL,
  event_ts BIGINT NOT NULL,
  ingest_ts BIGINT NOT NULL,
  payload_json JSONB NOT NULL,
  cursor_ref TEXT,
  schema_version TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_wallet_raw_event_wallet_ts ON wallet_raw_event(wallet_id, event_ts DESC);

CREATE TABLE IF NOT EXISTS wallet_canonical_event (
  id TEXT PRIMARY KEY,
  wallet_id TEXT NOT NULL REFERENCES wallet_master(id),
  chain TEXT NOT NULL,
  source_raw_event_id TEXT NOT NULL REFERENCES wallet_raw_event(id),
  event_type TEXT NOT NULL,
  asset_symbol TEXT,
  quote_symbol TEXT,
  direction_hint TEXT,
  qty DOUBLE PRECISION,
  notional_usd_est DOUBLE PRECISION,
  event_ts BIGINT NOT NULL,
  quality_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
  canonical_version TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_wallet_canonical_wallet_ts ON wallet_canonical_event(wallet_id, event_ts DESC);

CREATE TABLE IF NOT EXISTS wallet_inferred_event (
  id TEXT PRIMARY KEY,
  wallet_id TEXT NOT NULL REFERENCES wallet_master(id),
  canonical_event_id TEXT NOT NULL REFERENCES wallet_canonical_event(id),
  side TEXT NOT NULL,
  asset_scope TEXT NOT NULL,
  confidence_tier TEXT NOT NULL,
  confidence_score DOUBLE PRECISION NOT NULL,
  notional_usd_est DOUBLE PRECISION,
  price_ref DOUBLE PRECISION,
  event_ts BIGINT NOT NULL,
  inference_version TEXT NOT NULL,
  reason_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
  trace_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_wallet_inferred_wallet_ts ON wallet_inferred_event(wallet_id, event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_wallet_inferred_scope_conf ON wallet_inferred_event(asset_scope, confidence_tier, event_ts DESC);

CREATE TABLE IF NOT EXISTS wallet_classification (
  id BIGSERIAL PRIMARY KEY,
  wallet_id TEXT NOT NULL REFERENCES wallet_master(id),
  class_label TEXT NOT NULL,
  confidence_score DOUBLE PRECISION NOT NULL,
  excluded BOOLEAN NOT NULL DEFAULT FALSE,
  reason_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
  rule_version TEXT NOT NULL,
  effective_from BIGINT NOT NULL,
  effective_to BIGINT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_wallet_class_latest ON wallet_classification(wallet_id, effective_from DESC);

CREATE TABLE IF NOT EXISTS wallet_eligibility_snapshot (
  id BIGSERIAL PRIMARY KEY,
  wallet_id TEXT NOT NULL REFERENCES wallet_master(id),
  lookback_days INT NOT NULL,
  eligible BOOLEAN NOT NULL,
  failed_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
  metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  threshold_version TEXT NOT NULL,
  generated_at BIGINT NOT NULL,
  run_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wallet_eligibility_run ON wallet_eligibility_snapshot(run_id);

CREATE TABLE IF NOT EXISTS wallet_score_snapshot (
  id BIGSERIAL PRIMARY KEY,
  wallet_id TEXT NOT NULL REFERENCES wallet_master(id),
  window_days INT NOT NULL,
  score_total DOUBLE PRECISION NOT NULL,
  component_scores JSONB NOT NULL DEFAULT '{}'::jsonb,
  penalties_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  score_version TEXT NOT NULL,
  generated_at BIGINT NOT NULL,
  run_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wallet_score_window_run ON wallet_score_snapshot(window_days, run_id);

CREATE TABLE IF NOT EXISTS wallet_cohort_definition (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  version TEXT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO wallet_cohort_definition(id, name, description, params_json, version)
VALUES (
  'top_sol_active_wallets',
  'top_sol_active_wallets',
  'Top scored SOL-focused active wallets',
  '{"target_size":50,"refresh_hours":24,"buffer":15}'::jsonb,
  'v1'
)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS wallet_cohort_membership (
  id BIGSERIAL PRIMARY KEY,
  cohort_id TEXT NOT NULL REFERENCES wallet_cohort_definition(id),
  cohort_version TEXT NOT NULL,
  wallet_id TEXT NOT NULL REFERENCES wallet_master(id),
  rank INT NOT NULL,
  score_total DOUBLE PRECISION NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  reason_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  as_of_ts BIGINT NOT NULL,
  UNIQUE(cohort_id, cohort_version, wallet_id)
);
CREATE INDEX IF NOT EXISTS idx_wallet_cohort_membership_latest ON wallet_cohort_membership(cohort_id, as_of_ts DESC);

CREATE TABLE IF NOT EXISTS wallet_cohort_snapshot (
  id BIGSERIAL PRIMARY KEY,
  cohort_id TEXT NOT NULL REFERENCES wallet_cohort_definition(id),
  cohort_version TEXT NOT NULL,
  as_of_ts BIGINT NOT NULL,
  metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  signal_state TEXT,
  confidence_score DOUBLE PRECISION,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_wallet_cohort_snapshot_latest ON wallet_cohort_snapshot(cohort_id, as_of_ts DESC);

CREATE TABLE IF NOT EXISTS wallet_benchmark_signal (
  id BIGSERIAL PRIMARY KEY,
  cohort_id TEXT NOT NULL REFERENCES wallet_cohort_definition(id),
  signal_ts BIGINT NOT NULL,
  bias_state TEXT NOT NULL,
  bias_strength DOUBLE PRECISION NOT NULL,
  breadth_score DOUBLE PRECISION NOT NULL,
  concentration_score DOUBLE PRECISION NOT NULL,
  active_wallet_count INT NOT NULL,
  benchmark_confidence DOUBLE PRECISION NOT NULL,
  outputs_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  model_version TEXT NOT NULL,
  degraded_state TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_wallet_benchmark_signal_latest ON wallet_benchmark_signal(cohort_id, signal_ts DESC);

CREATE TABLE IF NOT EXISTS strategy_benchmark_alignment (
  id BIGSERIAL PRIMARY KEY,
  strategy_instance_id TEXT,
  trade_ref TEXT,
  scope TEXT NOT NULL,
  alignment_state TEXT NOT NULL,
  benchmark_signal_id BIGINT REFERENCES wallet_benchmark_signal(id),
  details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  ts BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_strategy_benchmark_alignment_scope_ts ON strategy_benchmark_alignment(scope, ts DESC);
