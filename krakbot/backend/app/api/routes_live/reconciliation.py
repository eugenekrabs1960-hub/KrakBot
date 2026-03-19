from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.reconciliation.live_reconcile import reconcile_positions

router = APIRouter(tags=["reconciliation"])


@router.post('/reconciliation/run')
def run_reconciliation(db: Session = Depends(get_db)):
    return reconcile_positions(db)
