from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.models.db_models import AutonomyRecommendationDB
from app.services.autonomy_stage1 import run_once
from app.services.experiments import SAFE_EXPERIMENT_KNOBS

router = APIRouter(tags=['autonomy'])


@router.post('/autonomy/stage1/run-once')
def autonomy_stage1_run_once(cycles: int = 8, db: Session = Depends(get_db)):
    return run_once(db, cycles=cycles)


@router.get('/autonomy/stage1/recent')
def autonomy_stage1_recent(limit: int = 10, db: Session = Depends(get_db)):
    rows = db.query(AutonomyRecommendationDB).order_by(desc(AutonomyRecommendationDB.created_at)).limit(max(1, min(limit, 100))).all()
    return {'items': [r.payload for r in rows]}


@router.get('/autonomy/stage1/latest')
def autonomy_stage1_latest(db: Session = Depends(get_db)):
    row = db.query(AutonomyRecommendationDB).order_by(desc(AutonomyRecommendationDB.created_at)).first()
    return {'item': row.payload if row else None}


@router.get('/autonomy/stage1/whitelist')
def autonomy_stage1_whitelist():
    return {'safe_experiment_knobs': SAFE_EXPERIMENT_KNOBS}
