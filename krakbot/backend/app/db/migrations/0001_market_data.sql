-- Krakbot Phase 1 market data tables

CREATE TABLE IF NOT EXISTS market_trades (
  id BIGSERIAL PRIMARY KEY,
  venue TEXT NOT NULL,
  market TEXT NOT NULL,
  instrument_type TEXT NOT NULL DEFAULT 'spot',
  side TEXT,
  price DOUBLE PRECISION NOT NULL,
  qty DOUBLE PRECISION NOT NULL,
  event_ts BIGINT NOT NULL,
  raw JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_trades_market_ts
  ON market_trades (market, event_ts DESC);

CREATE TABLE IF NOT EXISTS orderbook_snapshots (
  id BIGSERIAL PRIMARY KEY,
  venue TEXT NOT NULL,
  market TEXT NOT NULL,
  instrument_type TEXT NOT NULL DEFAULT 'spot',
  event_ts BIGINT NOT NULL,
  bids JSONB NOT NULL,
  asks JSONB NOT NULL,
  raw JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orderbook_snapshots_market_ts
  ON orderbook_snapshots (market, event_ts DESC);

CREATE TABLE IF NOT EXISTS candles (
  id BIGSERIAL PRIMARY KEY,
  venue TEXT NOT NULL,
  market TEXT NOT NULL,
  instrument_type TEXT NOT NULL DEFAULT 'spot',
  timeframe TEXT NOT NULL DEFAULT '1m',
  open_ts BIGINT NOT NULL,
  close_ts BIGINT NOT NULL,
  open DOUBLE PRECISION NOT NULL,
  high DOUBLE PRECISION NOT NULL,
  low DOUBLE PRECISION NOT NULL,
  close DOUBLE PRECISION NOT NULL,
  volume DOUBLE PRECISION NOT NULL DEFAULT 0,
  trade_count INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (venue, market, instrument_type, timeframe, open_ts)
);

CREATE INDEX IF NOT EXISTS idx_candles_market_open_ts
  ON candles (market, open_ts DESC);
