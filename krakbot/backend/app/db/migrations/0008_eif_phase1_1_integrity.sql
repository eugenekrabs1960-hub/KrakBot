-- Phase 8: EIF Phase 1.1 integrity hardening

ALTER TABLE eif_filter_decisions
  ADD COLUMN IF NOT EXISTS regime_snapshot_id BIGINT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_eif_filter_decisions_regime_snapshot_id'
  ) THEN
    ALTER TABLE eif_filter_decisions
      ADD CONSTRAINT fk_eif_filter_decisions_regime_snapshot_id
      FOREIGN KEY (regime_snapshot_id)
      REFERENCES eif_regime_snapshots(id)
      ON DELETE RESTRICT;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_eif_filter_decisions_regime_snapshot_id
  ON eif_filter_decisions(regime_snapshot_id);
