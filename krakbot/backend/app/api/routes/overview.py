from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.models import runtime_settings
from app.core.database import get_db
from app.services.journal.queries import recent_decisions
from app.services.execution.broker_router import get_broker

router = APIRouter(tags=['overview'])


@router.get('/overview')
def overview(db: Session = Depends(get_db)):
    broker = get_broker(runtime_settings.mode.execution_mode)
    decisions = recent_decisions(db, limit=10)
    return {
        'mode': runtime_settings.mode.model_dump(),
        'tracked_universe': runtime_settings.universe.model_dump(),
        'open_positions': broker.get_positions(),
        'recent_decisions': decisions,
        'recent_pnl_summary': {'realized_pnl_usd': 0.0, 'unrealized_pnl_usd': 0.0},
    }
