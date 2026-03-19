-- Wallet read-only signal pipeline (tracked-coin scoped)

CREATE TABLE IF NOT EXISTS wallet_events (
  event_id VARCHAR(64) PRIMARY KEY,
  coin VARCHAR(32) NOT NULL,
  symbol VARCHAR(64) NOT NULL,
  wallet_address VARCHAR(128) NOT NULL,
  side VARCHAR(16) NOT NULL,
  notional_usd DOUBLE PRECISION NOT NULL,
  event_ts TIMESTAMP NOT NULL,
  bucket_ts INTEGER NOT NULL,
  source VARCHAR(64) NOT NULL,
  payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wallet_events_coin_ts ON wallet_events (coin, event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_wallet_events_symbol_ts ON wallet_events (symbol, event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_wallet_events_bucket ON wallet_events (bucket_ts);

CREATE TABLE IF NOT EXISTS wallet_summaries (
  summary_id VARCHAR(64) PRIMARY KEY,
  coin VARCHAR(32) NOT NULL,
  symbol VARCHAR(64) NOT NULL,
  generated_at TIMESTAMP NOT NULL,
  payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wallet_summaries_coin_ts ON wallet_summaries (coin, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_wallet_summaries_symbol_ts ON wallet_summaries (symbol, generated_at DESC);
