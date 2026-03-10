-- Phase 6: create missing performance_snapshots table + seed default SOL/USD strategy instances

CREATE TABLE IF NOT EXISTS performance_snapshots (
  id BIGSERIAL PRIMARY KEY,
  strategy_instance_id TEXT NOT NULL REFERENCES strategy_instances(id),
  pnl_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
  drawdown_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
  win_rate_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
  trade_count INTEGER NOT NULL DEFAULT 0,
  ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_performance_snapshots_sid_ts
  ON performance_snapshots(strategy_instance_id, ts DESC);

INSERT INTO strategy_instances(id, strategy_id, market, instrument_type, enabled, status, params)
VALUES
  ('trend_following_sol_usd', 'strat_trend_following', 'SOL/USD', 'spot', true, 'idle', '{}'::jsonb),
  ('mean_reversion_sol_usd', 'strat_mean_reversion', 'SOL/USD', 'spot', true, 'idle', '{}'::jsonb),
  ('breakout_sol_usd', 'strat_breakout', 'SOL/USD', 'spot', true, 'idle', '{}'::jsonb)
ON CONFLICT (id) DO NOTHING;

INSERT INTO paper_portfolios(id, strategy_instance_id, base_currency, starting_equity_usd, equity_usd)
VALUES
  ('port_trend_following_sol_usd', 'trend_following_sol_usd', 'USD', 10000, 10000),
  ('port_mean_reversion_sol_usd', 'mean_reversion_sol_usd', 'USD', 10000, 10000),
  ('port_breakout_sol_usd', 'breakout_sol_usd', 'USD', 10000, 10000)
ON CONFLICT (strategy_instance_id) DO NOTHING;
