-- Phase 9: EIF Phase 2 filter trace + engine decision metadata

ALTER TABLE eif_filter_decisions
  ADD COLUMN IF NOT EXISTS trace JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS precedence_stage TEXT,
  ADD COLUMN IF NOT EXISTS shadow_mode BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS enforce_mode BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS filter_engine_version TEXT NOT NULL DEFAULT 'v1';

CREATE INDEX IF NOT EXISTS idx_eif_filter_decisions_allowed_ts
  ON eif_filter_decisions(allowed, ts DESC);

CREATE INDEX IF NOT EXISTS idx_eif_filter_decisions_precedence_stage_ts
  ON eif_filter_decisions(precedence_stage, ts DESC);
