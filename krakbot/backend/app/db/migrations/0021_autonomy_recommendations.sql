-- 0021_autonomy_recommendations.sql
CREATE TABLE IF NOT EXISTS autonomy_recommendations (
  recommendation_id VARCHAR(64) PRIMARY KEY,
  created_at TIMESTAMP NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_autonomy_recommendations_created ON autonomy_recommendations(created_at DESC);
