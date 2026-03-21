CREATE TABLE IF NOT EXISTS autonomy_cooldowns (
  change_path VARCHAR(128) PRIMARY KEY,
  cooldown_until TIMESTAMP NOT NULL,
  reason VARCHAR(128) NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_autonomy_cooldowns_until ON autonomy_cooldowns(cooldown_until DESC);
