-- Phase 5: config-driven market registry + strategy market assignments

CREATE TABLE IF NOT EXISTS market_registry (
  id TEXT PRIMARY KEY,
  venue TEXT NOT NULL,
  symbol TEXT NOT NULL,
  base_asset TEXT NOT NULL,
  quote_asset TEXT NOT NULL,
  instrument_type TEXT NOT NULL DEFAULT 'spot',
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (venue, symbol, instrument_type)
);

CREATE TABLE IF NOT EXISTS strategy_markets (
  strategy_instance_id TEXT NOT NULL REFERENCES strategy_instances(id),
  market_id TEXT NOT NULL REFERENCES market_registry(id),
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY(strategy_instance_id, market_id)
);

INSERT INTO market_registry(id, venue, symbol, base_asset, quote_asset, instrument_type, enabled)
VALUES
  ('mkt_kraken_SOLUSD_spot', 'kraken', 'SOL/USD', 'SOL', 'USD', 'spot', true),
  ('mkt_kraken_BTCUSD_spot', 'kraken', 'BTC/USD', 'BTC', 'USD', 'spot', false),
  ('mkt_kraken_ETHUSD_spot', 'kraken', 'ETH/USD', 'ETH', 'USD', 'spot', false)
ON CONFLICT (id) DO NOTHING;
