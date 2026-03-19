from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.models import runtime_settings
from app.core.database import get_db
from app.models.db_models import WalletSummaryDB
from app.services.journal.queries import recent_decisions
from app.services.execution.broker_router import get_broker

router = APIRouter(tags=['overview'])


@router.get('/overview')
def overview(db: Session = Depends(get_db)):
    broker = get_broker(runtime_settings.mode.execution_mode)
    decisions = recent_decisions(db, limit=10)

    wallet_items = []
    for coin in runtime_settings.universe.tracked_coins:
        row = (
            db.query(WalletSummaryDB)
            .filter(WalletSummaryDB.coin == coin)
            .order_by(desc(WalletSummaryDB.generated_at))
            .first()
        )
        wallet_items.append({
            'coin': coin,
            'symbol': f'{coin}-PERP',
            'summary': row.payload if row else None,
            'generated_at': row.generated_at if row else None,
        })

    return {
        'mode': runtime_settings.mode.model_dump(),
        'tracked_universe': runtime_settings.universe.model_dump(),
        'open_positions': broker.get_positions(),
        'recent_decisions': decisions,
        'wallet_summaries': wallet_items,
        'recent_pnl_summary': {'realized_pnl_usd': 0.0, 'unrealized_pnl_usd': 0.0},
    }
