from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.models import runtime_settings
from app.core.database import get_db
from app.models.db_models import WalletEventDB, WalletSummaryDB

router = APIRouter(tags=["wallets"])


@router.get('/wallets/summary')
def wallet_summary(db: Session = Depends(get_db)):
    items = []
    for coin in runtime_settings.universe.tracked_coins:
        row = (
            db.query(WalletSummaryDB)
            .filter(WalletSummaryDB.coin == coin)
            .order_by(desc(WalletSummaryDB.generated_at))
            .first()
        )
        if row:
            items.append({
                "coin": coin,
                "symbol": row.symbol,
                "generated_at": row.generated_at,
                "summary": row.payload,
            })
        else:
            items.append({
                "coin": coin,
                "symbol": f"{coin}-PERP",
                "generated_at": None,
                "summary": None,
            })
    return {"items": items}


@router.get('/wallets/events')
def wallet_events(limit: int = 100, db: Session = Depends(get_db)):
    rows = (
        db.query(WalletEventDB)
        .filter(WalletEventDB.coin.in_(runtime_settings.universe.tracked_coins))
        .order_by(desc(WalletEventDB.event_ts))
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return {
        "items": [
            {
                "event_id": r.event_id,
                "coin": r.coin,
                "symbol": r.symbol,
                "wallet_address": r.wallet_address,
                "side": r.side,
                "notional_usd": r.notional_usd,
                "event_ts": r.event_ts,
                "source": r.source,
            }
            for r in rows
        ]
    }
