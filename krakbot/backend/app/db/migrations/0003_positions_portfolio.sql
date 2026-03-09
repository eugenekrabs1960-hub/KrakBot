-- Phase 3: positions + portfolio balances + metrics snapshots

CREATE TABLE IF NOT EXISTS positions (
  id TEXT PRIMARY KEY,
  strategy_instance_id TEXT NOT NULL REFERENCES strategy_instances(id),
  market TEXT NOT NULL,
  side TEXT NOT NULL DEFAULT 'long',
  qty DOUBLE PRECISION NOT NULL DEFAULT 0,
  avg_entry_price DOUBLE PRECISION NOT NULL DEFAULT 0,
  realized_pnl_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(strategy_instance_id, market)
);

CREATE TABLE IF NOT EXISTS portfolio_balances (
  id BIGSERIAL PRIMARY KEY,
  strategy_instance_id TEXT NOT NULL REFERENCES strategy_instances(id),
  asset TEXT NOT NULL,
  free DOUBLE PRECISION NOT NULL DEFAULT 0,
  locked DOUBLE PRECISION NOT NULL DEFAULT 0,
  equity_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
  ts BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_portfolio_balances_sid_ts
  ON portfolio_balances(strategy_instance_id, ts DESC);

CREATE TABLE IF NOT EXISTS strategy_events (
  id BIGSERIAL PRIMARY KEY,
  strategy_instance_id TEXT NOT NULL REFERENCES strategy_instances(id),
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  ts BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_strategy_events_sid_ts
  ON strategy_events(strategy_instance_id, ts DESC);
