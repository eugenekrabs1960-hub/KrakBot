from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.journal.queries import recent_decisions, recent_packets, recent_policy, recent_exec
from app.services.decision_engine import run_decision_cycle

router = APIRouter(tags=["decisions"])


@router.post('/decisions/run-cycle')
def run_cycle(db: Session = Depends(get_db)):
    return run_decision_cycle(db)


@router.get('/decisions/recent')
def decisions_recent(limit: int = 50, db: Session = Depends(get_db)):
    return {
        'packets': recent_packets(db, limit),
        'decisions': recent_decisions(db, limit),
        'policy': recent_policy(db, limit),
        'execution': recent_exec(db, limit),
    }
