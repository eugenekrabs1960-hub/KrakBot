from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/snapshot")
def snapshot(db: Session = Depends(get_db)):
    row = db.execute(
        text(
            """
            SELECT market, instrument_type, price, event_ts
            FROM market_trades
            ORDER BY id DESC
            LIMIT 1
            """
        )
    ).mappings().first()
    if not row:
        return {
            "venue": "kraken",
            "market": "SOL/USD",
            "instrument_type": "spot",
            "last_price": None,
            "ts": None,
        }
    return {
        "venue": "kraken",
        "market": row["market"],
        "instrument_type": row["instrument_type"],
        "last_price": row["price"],
        "ts": row["event_ts"],
    }


@router.get("/trades")
def recent_trades(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            """
            SELECT market, side, price, qty, event_ts
            FROM market_trades
            ORDER BY id DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.get("/orderbook")
def orderbook(db: Session = Depends(get_db)):
    row = db.execute(
        text(
            """
            SELECT market, bids, asks, event_ts
            FROM orderbook_snapshots
            ORDER BY id DESC
            LIMIT 1
            """
        )
    ).mappings().first()
    return {"item": dict(row) if row else None}


@router.get("/candles")
def candles(limit: int = 200, db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            """
            SELECT market, timeframe, open_ts, close_ts, open, high, low, close, volume, trade_count
            FROM candles
            ORDER BY open_ts DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()
    return {"items": [dict(r) for r in rows]}
