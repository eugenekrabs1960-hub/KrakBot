CREATE TABLE IF NOT EXISTS hyperliquid_market_mids (
  id BIGSERIAL PRIMARY KEY,
  ts BIGINT NOT NULL,
  environment TEXT NOT NULL,
  symbol TEXT NOT NULL,
  mid_price DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hl_market_mids_symbol_ts ON hyperliquid_market_mids(symbol, ts DESC);

CREATE TABLE IF NOT EXISTS hyperliquid_market_meta_snapshots (
  id BIGSERIAL PRIMARY KEY,
  ts BIGINT NOT NULL,
  environment TEXT NOT NULL,
  symbols_count INT NOT NULL,
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS hyperliquid_training_features (
  id BIGSERIAL PRIMARY KEY,
  ts BIGINT NOT NULL,
  environment TEXT NOT NULL,
  symbol TEXT NOT NULL,
  mid_price DOUBLE PRECISION NOT NULL,
  ret_1 DOUBLE PRECISION,
  ret_5 DOUBLE PRECISION,
  ret_15 DOUBLE PRECISION,
  source TEXT NOT NULL DEFAULT 'hyperliquid_public_v1'
);
CREATE INDEX IF NOT EXISTS idx_hl_training_features_symbol_ts ON hyperliquid_training_features(symbol, ts DESC);
