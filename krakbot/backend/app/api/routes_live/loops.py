from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.services.loops.scheduler import loop_scheduler
from app.core.database import get_db
from app.models.db_models import LoopRunDB

router = APIRouter(tags=["loops"])


@router.get('/loops/status')
def loops_status():
    return {
        "running": True,
        "tracked_scores": list(loop_scheduler.last_feature_scores.keys()),
        "feature_count": len(loop_scheduler.last_feature_scores),
        "last_feature_run_at": loop_scheduler.last_feature_run_at,
        "last_decision_run_at": loop_scheduler.last_decision_run_at,
        "last_error": loop_scheduler.last_error,
    }


@router.get('/loops/history')
def loops_history(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(LoopRunDB).order_by(desc(LoopRunDB.started_at)).limit(max(1, min(limit, 500))).all()
    return {"items": [
        {
            "run_id": r.run_id,
            "loop_type": r.loop_type,
            "status": r.status,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "duration_ms": r.duration_ms,
            "message": r.message,
        }
        for r in rows
    ]}
