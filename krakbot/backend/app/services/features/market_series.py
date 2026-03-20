from __future__ import annotations

from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.models.db_models import MarketSnapshot1mDB


def persist_market_snapshot(db: Session, market: dict) -> None:
    row = MarketSnapshot1mDB(
        ts=datetime.now(timezone.utc),
        coin=market.get('coin') or market.get('symbol','UNK').replace('-PERP',''),
        symbol=market.get('symbol') or 'UNK-PERP',
        mid_price=float(market.get('last_price') or 0.0),
        mark_price=float(market.get('mark_price') or 0.0),
        index_price=float(market.get('index_price') or 0.0),
        spread_bps=float(market.get('spread_bps') or 0.0),
        funding_rate=float(market.get('funding_rate') or 0.0),
        open_interest_usd=float(market.get('open_interest_usd') or 0.0),
        volume_5m_usd=float(market.get('volume_5m_usd') or 0.0),
        volume_1h_usd=float(market.get('volume_1h_usd') or 0.0),
        source=str(market.get('source') or 'unknown'),
    )
    db.add(row)


def load_market_series(db: Session, coin: str, lookback_hours: int = 6) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    rows = (
        db.query(MarketSnapshot1mDB)
        .filter(MarketSnapshot1mDB.coin == coin, MarketSnapshot1mDB.ts >= since)
        .order_by(MarketSnapshot1mDB.ts.asc())
        .all()
    )
    return [
        {
            'ts': r.ts,
            'px': float(r.mark_price or r.mid_price or 0.0),
            'vol5': float(r.volume_5m_usd or 0.0),
            'oi': float(r.open_interest_usd or 0.0),
            'funding': float(r.funding_rate or 0.0),
        }
        for r in rows
    ]
