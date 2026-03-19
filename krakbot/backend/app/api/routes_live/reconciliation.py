from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.services.reconcile.live_reconcile import reconcile_positions
from app.models.db_models import ReconciliationRunDB

router = APIRouter(tags=["reconciliation"])


@router.post('/reconciliation/run')
def run_reconciliation(db: Session = Depends(get_db)):
    return reconcile_positions(db)


@router.get('/reconciliation/history')
def reconciliation_history(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(ReconciliationRunDB).order_by(desc(ReconciliationRunDB.created_at)).limit(max(1, min(limit, 500))).all()
    return {"items": [
        {
            "recon_id": r.recon_id,
            "mode": r.mode,
            "broker_position_count": r.broker_position_count,
            "local_position_count": r.local_position_count,
            "drift_count": r.drift_count,
            "status": r.status,
            "payload": r.payload,
            "created_at": r.created_at,
        }
        for r in rows
    ]}
