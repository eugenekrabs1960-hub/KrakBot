from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.reconciliation import ReconciliationService

router = APIRouter(prefix='/reliability', tags=['reliability'])


@router.post('/reconcile/all')
def reconcile_all(db: Session = Depends(get_db)):
    svc = ReconciliationService()
    return svc.run_global_recon(db)


@router.post('/reconcile/{strategy_instance_id}')
def reconcile_one(strategy_instance_id: str, db: Session = Depends(get_db)):
    svc = ReconciliationService()
    return svc.run_strategy_recon(db, strategy_instance_id)


@router.get('/reconciliations')
def list_reconciliations(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            """
            SELECT id, strategy_instance_id, kind, status, details, ts
            FROM reconciliations
            ORDER BY id DESC
            LIMIT :limit
            """
        ),
        {'limit': limit},
    ).mappings().all()
    return {'items': [dict(r) for r in rows]}
