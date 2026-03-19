-- Create dedicated lab positions table to avoid collision with legacy positions schema

CREATE TABLE IF NOT EXISTS lab_positions (
  symbol VARCHAR(64) PRIMARY KEY,
  qty DOUBLE PRECISION NOT NULL DEFAULT 0,
  avg_entry DOUBLE PRECISION NOT NULL DEFAULT 0,
  mode VARCHAR(32) NOT NULL DEFAULT 'paper',
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Optional backfill if legacy positions table happens to contain compatible columns
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'positions'
  )
  AND EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'positions' AND column_name = 'symbol'
  ) THEN
    INSERT INTO lab_positions(symbol, qty, avg_entry, mode, updated_at)
    SELECT symbol, COALESCE(qty, 0), COALESCE(avg_entry, 0), COALESCE(mode, 'paper'), COALESCE(updated_at, CURRENT_TIMESTAMP)
    FROM positions
    ON CONFLICT (symbol) DO NOTHING;
  END IF;
END $$;
