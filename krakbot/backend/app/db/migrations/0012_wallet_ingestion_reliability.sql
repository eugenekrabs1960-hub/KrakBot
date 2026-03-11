-- Phase 6 reliability hardening for wallet ingestion continuity

CREATE UNIQUE INDEX IF NOT EXISTS uq_wallet_raw_event_provider_event
  ON wallet_raw_event(provider, provider_event_id)
  WHERE provider_event_id IS NOT NULL;
