import time
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.eif_vocab import REGIME_DIMENSIONS, REGIME_VERSION


class EIFRegimeSnapshotBuilder:
    """Deterministic, interpretable regime snapshot builder (Phase 1)."""

    version = REGIME_VERSION

    def build(self, db: Session, market: str, strategy_instance_id: str | None = None) -> dict:
        now_ms = int(time.time() * 1000)
        row = db.execute(
            text(
                """
                WITH w AS (
                  SELECT price, qty, event_ts
                  FROM market_trades
                  WHERE market = :market
                    AND event_ts >= :from_ts
                )
                SELECT
                  COUNT(*)::int AS sample_size,
                  AVG(price) AS avg_price,
                  MIN(price) AS min_price,
                  MAX(price) AS max_price,
                  AVG(qty) AS avg_qty,
                  SUM(qty) AS total_qty,
                  (SELECT price FROM w ORDER BY event_ts ASC LIMIT 1) AS first_price,
                  (SELECT price FROM w ORDER BY event_ts DESC LIMIT 1) AS last_price
                FROM w
                """
            ),
            {"market": market, "from_ts": now_ms - 5 * 60 * 1000},
        ).mappings().first()

        sample_size = int((row or {}).get("sample_size") or 0)
        if sample_size == 0:
            return {
                "strategy_instance_id": strategy_instance_id,
                "market": market,
                "regime_version": self.version,
                "trend": "unknown",
                "volatility": "unknown",
                "liquidity": "unknown",
                "session_structure": "unknown",
                "sample_size": 0,
                "features": {"reason": "no_recent_market_trades"},
                "captured_ts": now_ms,
            }

        avg_price = float(row["avg_price"] or 0.0)
        min_price = float(row["min_price"] or avg_price)
        max_price = float(row["max_price"] or avg_price)
        avg_qty = float(row["avg_qty"] or 0.0)
        total_qty = float(row["total_qty"] or 0.0)

        price_span_pct = ((max_price - min_price) / avg_price) if avg_price > 0 else 0.0
        if price_span_pct > 0.01:
            volatility = "high"
        elif price_span_pct < 0.003:
            volatility = "low"
        else:
            volatility = "normal"

        first_price = float(row["first_price"] or avg_price)
        last_price = float(row["last_price"] or avg_price)
        trend = "flat"
        if first_price > 0:
            change = (last_price - first_price) / first_price
            if change > 0.003:
                trend = "up"
            elif change < -0.003:
                trend = "down"

        if total_qty > 200:
            liquidity = "thick"
        elif total_qty < 20:
            liquidity = "thin"
        else:
            liquidity = "normal"

        session_structure = "active" if sample_size >= 20 else "quiet"

        for dim, options in REGIME_DIMENSIONS.items():
            val = {
                "trend": trend,
                "volatility": volatility,
                "liquidity": liquidity,
                "session_structure": session_structure,
            }[dim]
            if val not in options:
                raise ValueError(f"invalid regime state for {dim}: {val}")

        return {
            "strategy_instance_id": strategy_instance_id,
            "market": market,
            "regime_version": self.version,
            "trend": trend,
            "volatility": volatility,
            "liquidity": liquidity,
            "session_structure": session_structure,
            "sample_size": sample_size,
            "features": {
                "price_span_pct": price_span_pct,
                "avg_qty": avg_qty,
                "total_qty": total_qty,
            },
            "captured_ts": now_ms,
        }
