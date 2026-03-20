-- 0020_market_snapshots_1m.sql
CREATE TABLE IF NOT EXISTS market_snapshots_1m (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMP NOT NULL,
  coin VARCHAR(16) NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  mid_price DOUBLE PRECISION,
  mark_price DOUBLE PRECISION,
  index_price DOUBLE PRECISION,
  spread_bps DOUBLE PRECISION,
  funding_rate DOUBLE PRECISION,
  open_interest_usd DOUBLE PRECISION,
  volume_5m_usd DOUBLE PRECISION,
  volume_1h_usd DOUBLE PRECISION,
  source VARCHAR(64) NOT NULL DEFAULT 'unknown'
);

CREATE INDEX IF NOT EXISTS idx_market_snapshots_1m_coin_ts ON market_snapshots_1m(coin, ts DESC);
CREATE INDEX IF NOT EXISTS idx_market_snapshots_1m_ts ON market_snapshots_1m(ts DESC);
