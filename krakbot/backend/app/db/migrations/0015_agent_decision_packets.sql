CREATE TABLE IF NOT EXISTS agent_decision_packets (
  id BIGSERIAL PRIMARY KEY,
  ts BIGINT NOT NULL,
  agent_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  action TEXT NOT NULL,
  confidence DOUBLE PRECISION,
  rationale TEXT,
  context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  risk_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  execution_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  outcome_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_ts ON agent_decision_packets(ts DESC);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_agent_symbol ON agent_decision_packets(agent_id, symbol, ts DESC);
