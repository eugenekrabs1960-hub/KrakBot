CREATE TABLE IF NOT EXISTS agent_virtual_trades (
  id BIGSERIAL PRIMARY KEY,
  agent_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  leverage DOUBLE PRECISION NOT NULL,
  allocation_pct DOUBLE PRECISION NOT NULL,
  margin_usd DOUBLE PRECISION NOT NULL,
  entry_price DOUBLE PRECISION NOT NULL,
  exit_price DOUBLE PRECISION,
  qty DOUBLE PRECISION NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  rationale TEXT,
  opened_at_ms BIGINT NOT NULL,
  closed_at_ms BIGINT,
  realized_pnl_usd DOUBLE PRECISION,
  balance_after_usd DOUBLE PRECISION,
  meta_json JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_virtual_trades_agent_open ON agent_virtual_trades(agent_id, status, id DESC);
CREATE INDEX IF NOT EXISTS idx_agent_virtual_trades_agent_time ON agent_virtual_trades(agent_id, opened_at_ms DESC);
