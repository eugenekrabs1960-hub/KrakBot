import json
import time
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings


class EIFScorecardService:
    @property
    def enabled(self) -> bool:
        return settings.eif_scorecard_compute_enabled

    def compute_snapshot(self, db: Session, strategy_instance_id: str, market: str) -> dict | None:
        if not self.enabled:
            return None

        window = self._compute_window(db, strategy_instance_id, market, lookback_limit=200)
        baseline = self._compute_window(db, strategy_instance_id, market, lookback_limit=1000)

        payload = {
            "rolling": window,
            "baseline": baseline,
        }
        ts = int(time.time() * 1000)
        db.execute(
            text(
                """
                INSERT INTO eif_scorecard_snapshots(
                    strategy_instance_id, market, snapshot_type, window_label,
                    win_rate, expectancy, pnl_per_trade, sample_size, payload, ts
                ) VALUES
                    (:sid, :market, 'rolling', 'last_200_trades', :r_wr, :r_ex, :r_ppt, :r_n, CAST(:payload AS jsonb), :ts),
                    (:sid, :market, 'baseline', 'last_1000_trades', :b_wr, :b_ex, :b_ppt, :b_n, CAST(:payload AS jsonb), :ts)
                """
            ),
            {
                "sid": strategy_instance_id,
                "market": market,
                "r_wr": window["win_rate"],
                "r_ex": window["expectancy"],
                "r_ppt": window["pnl_per_trade"],
                "r_n": window["sample_size"],
                "b_wr": baseline["win_rate"],
                "b_ex": baseline["expectancy"],
                "b_ppt": baseline["pnl_per_trade"],
                "b_n": baseline["sample_size"],
                "payload": json.dumps(payload),
                "ts": ts,
            },
        )
        db.commit()
        return payload

    def _compute_window(self, db: Session, strategy_instance_id: str, market: str, lookback_limit: int) -> dict:
        row = db.execute(
            text(
                """
                WITH recent AS (
                    SELECT side, COALESCE(realized_pnl_usd, 0) AS pnl
                    FROM executions
                    WHERE strategy_instance_id = :sid AND market = :market
                    ORDER BY event_ts DESC
                    LIMIT :n
                )
                SELECT
                    COUNT(*)::int AS sample_size,
                    COALESCE(AVG(pnl), 0) AS pnl_per_trade,
                    COALESCE(AVG(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END), 0) AS win_rate,
                    COALESCE(AVG(pnl), 0) AS expectancy
                FROM recent
                """
            ),
            {"sid": strategy_instance_id, "market": market, "n": lookback_limit},
        ).mappings().first()

        return {
            "sample_size": int((row or {}).get("sample_size") or 0),
            "pnl_per_trade": float((row or {}).get("pnl_per_trade") or 0.0),
            "win_rate": float((row or {}).get("win_rate") or 0.0),
            "expectancy": float((row or {}).get("expectancy") or 0.0),
        }


eif_scorecard = EIFScorecardService()
