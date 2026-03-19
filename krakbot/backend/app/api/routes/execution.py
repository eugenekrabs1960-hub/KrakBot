from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.models import runtime_settings
from app.core.config import settings
from app.core.database import get_db
from app.models.db_models import LiveRelayRequestDB
from app.services.execution.broker_router import get_broker

router = APIRouter(tags=['execution'])


@router.get('/execution/health')
def execution_health():
    return {
        "mode": runtime_settings.mode.execution_mode,
        "live_armed": runtime_settings.mode.live_armed,
        "relay_configured": bool(settings.hyperliquid_order_relay_url),
        "account_configured": bool(settings.hyperliquid_account_address),
    }


@router.get('/execution/relay/history')
def relay_history(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(LiveRelayRequestDB).order_by(desc(LiveRelayRequestDB.created_at)).limit(max(1, min(limit, 500))).all()
    return {"items": [
        {
            "idempotency_key": r.idempotency_key,
            "action": r.action,
            "status": r.status,
            "payload": r.payload,
            "response": r.response,
            "created_at": r.created_at,
        }
        for r in rows
    ]}


@router.post('/execution/flatten-all')
def flatten_all():
    broker = get_broker(runtime_settings.mode.execution_mode)
    return broker.flatten_all_positions()
