-- Phase 7: EIF Phase 1 data foundation + capture tables (shadow mode, no enforcement)

CREATE TABLE IF NOT EXISTS eif_regime_snapshots (
  id BIGSERIAL PRIMARY KEY,
  strategy_instance_id TEXT REFERENCES strategy_instances(id),
  market TEXT NOT NULL,
  regime_version TEXT NOT NULL,
  trend TEXT NOT NULL DEFAULT 'unknown',
  volatility TEXT NOT NULL DEFAULT 'unknown',
  liquidity TEXT NOT NULL DEFAULT 'unknown',
  session_structure TEXT NOT NULL DEFAULT 'unknown',
  sample_size INTEGER NOT NULL DEFAULT 0,
  features JSONB NOT NULL DEFAULT '{}'::jsonb,
  captured_ts BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eif_regime_market_ts
  ON eif_regime_snapshots(market, captured_ts DESC);

CREATE INDEX IF NOT EXISTS idx_eif_regime_sid_ts
  ON eif_regime_snapshots(strategy_instance_id, captured_ts DESC);

CREATE TABLE IF NOT EXISTS eif_trade_context_events (
  id BIGSERIAL PRIMARY KEY,
  strategy_instance_id TEXT REFERENCES strategy_instances(id),
  market TEXT NOT NULL,
  event_type TEXT NOT NULL,
  side TEXT,
  qty DOUBLE PRECISION,
  price DOUBLE PRECISION,
  pnl_usd DOUBLE PRECISION,
  tags_version TEXT NOT NULL,
  tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  context JSONB NOT NULL DEFAULT '{}'::jsonb,
  ts BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eif_trade_events_sid_ts
  ON eif_trade_context_events(strategy_instance_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_eif_trade_events_market_ts
  ON eif_trade_context_events(market, ts DESC);

CREATE TABLE IF NOT EXISTS eif_filter_decisions (
  id BIGSERIAL PRIMARY KEY,
  strategy_instance_id TEXT REFERENCES strategy_instances(id),
  market TEXT NOT NULL,
  event_type TEXT NOT NULL,
  decision TEXT NOT NULL,
  reason_code TEXT NOT NULL,
  allowed BOOLEAN NOT NULL DEFAULT FALSE,
  reason_code_version TEXT NOT NULL,
  tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  regime_version TEXT NOT NULL,
  regime_snapshot_ts BIGINT NOT NULL,
  ts BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eif_filter_decisions_sid_ts
  ON eif_filter_decisions(strategy_instance_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_eif_filter_decisions_reason_ts
  ON eif_filter_decisions(reason_code, ts DESC);

CREATE TABLE IF NOT EXISTS eif_scorecard_snapshots (
  id BIGSERIAL PRIMARY KEY,
  strategy_instance_id TEXT REFERENCES strategy_instances(id),
  market TEXT NOT NULL,
  snapshot_type TEXT NOT NULL,
  window_label TEXT NOT NULL,
  win_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
  expectancy DOUBLE PRECISION NOT NULL DEFAULT 0,
  pnl_per_trade DOUBLE PRECISION NOT NULL DEFAULT 0,
  sample_size INTEGER NOT NULL DEFAULT 0,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  ts BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eif_scorecard_sid_ts
  ON eif_scorecard_snapshots(strategy_instance_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_eif_scorecard_type_ts
  ON eif_scorecard_snapshots(snapshot_type, ts DESC);
