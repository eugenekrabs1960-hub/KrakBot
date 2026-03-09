-- Phase 2: strategy registry + runtime state + canonical execution tables

CREATE TABLE IF NOT EXISTS strategies (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  family TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_instances (
  id TEXT PRIMARY KEY,
  strategy_id TEXT NOT NULL REFERENCES strategies(id),
  market TEXT NOT NULL,
  instrument_type TEXT NOT NULL DEFAULT 'spot',
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  status TEXT NOT NULL DEFAULT 'idle',
  params JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paper_portfolios (
  id TEXT PRIMARY KEY,
  strategy_instance_id TEXT NOT NULL UNIQUE REFERENCES strategy_instances(id),
  base_currency TEXT NOT NULL DEFAULT 'USD',
  starting_equity_usd DOUBLE PRECISION NOT NULL DEFAULT 10000,
  equity_usd DOUBLE PRECISION NOT NULL DEFAULT 10000,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS system_state (
  key TEXT PRIMARY KEY,
  value JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY,
  strategy_instance_id TEXT NOT NULL REFERENCES strategy_instances(id),
  venue TEXT NOT NULL,
  market TEXT NOT NULL,
  instrument_type TEXT NOT NULL DEFAULT 'spot',
  side TEXT NOT NULL,
  order_type TEXT NOT NULL,
  qty DOUBLE PRECISION NOT NULL,
  limit_price DOUBLE PRECISION,
  status TEXT NOT NULL,
  engine TEXT NOT NULL,
  engine_order_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_strategy_created
  ON orders(strategy_instance_id, created_at DESC);

CREATE TABLE IF NOT EXISTS executions (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(id),
  strategy_instance_id TEXT NOT NULL REFERENCES strategy_instances(id),
  venue TEXT NOT NULL,
  market TEXT NOT NULL,
  side TEXT NOT NULL,
  fill_price DOUBLE PRECISION NOT NULL,
  fill_qty DOUBLE PRECISION NOT NULL,
  fee_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
  realized_pnl_usd DOUBLE PRECISION,
  engine TEXT NOT NULL,
  engine_trade_id TEXT,
  event_ts BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_executions_strategy_eventts
  ON executions(strategy_instance_id, event_ts DESC);

INSERT INTO strategies(id, name, family)
VALUES
  ('strat_trend_following', 'trend_following', 'trend'),
  ('strat_mean_reversion', 'mean_reversion', 'mean_reversion'),
  ('strat_breakout', 'breakout', 'volatility')
ON CONFLICT (id) DO NOTHING;

INSERT INTO system_state(key, value)
VALUES ('bot', '{"state":"stopped"}'::jsonb)
ON CONFLICT (key) DO NOTHING;
