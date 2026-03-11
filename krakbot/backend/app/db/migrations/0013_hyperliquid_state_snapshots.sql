CREATE TABLE IF NOT EXISTS hyperliquid_account_snapshots (
  id BIGSERIAL PRIMARY KEY,
  ts BIGINT NOT NULL,
  environment TEXT NOT NULL,
  equity_usd DOUBLE PRECISION NOT NULL,
  available_margin_usd DOUBLE PRECISION,
  maintenance_margin_usd DOUBLE PRECISION,
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_hl_account_snapshots_ts ON hyperliquid_account_snapshots(ts DESC);

CREATE TABLE IF NOT EXISTS hyperliquid_position_snapshots (
  id BIGSERIAL PRIMARY KEY,
  ts BIGINT NOT NULL,
  environment TEXT NOT NULL,
  market TEXT NOT NULL,
  qty DOUBLE PRECISION NOT NULL,
  avg_entry_price DOUBLE PRECISION NOT NULL,
  realized_pnl_usd DOUBLE PRECISION NOT NULL,
  unrealized_pnl_usd DOUBLE PRECISION NOT NULL,
  leverage DOUBLE PRECISION,
  liquidation_price DOUBLE PRECISION,
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_hl_position_snapshots_ts ON hyperliquid_position_snapshots(ts DESC);
CREATE INDEX IF NOT EXISTS idx_hl_position_snapshots_market_ts ON hyperliquid_position_snapshots(market, ts DESC);
