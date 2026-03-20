from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.models.db_models import ExperimentRunDB
from app.services.experiments import run_experiment

router = APIRouter(tags=['experiments'])


class ExperimentSpec(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    change_path: str
    change_value: object
    cycles: int = 40


@router.post('/experiments/run')
def experiments_run(spec: ExperimentSpec, db: Session = Depends(get_db)):
    try:
        out = run_experiment(
            db,
            name=spec.name,
            change_path=spec.change_path,
            change_value=spec.change_value,
            cycles=spec.cycles,
        )
        return out
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/experiments/runs')
def experiments_runs(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.query(ExperimentRunDB).order_by(desc(ExperimentRunDB.created_at)).limit(max(1, min(limit, 200))).all()
    return {
        'items': [
            {
                'run_id': r.run_id,
                'name': r.name,
                'status': r.status,
                'created_at': r.created_at,
                'classification': (r.payload or {}).get('classification'),
                'spec': (r.payload or {}).get('spec'),
            }
            for r in rows
        ]
    }


@router.get('/experiments/runs/{run_id}')
def experiments_run_detail(run_id: str, db: Session = Depends(get_db)):
    row = db.get(ExperimentRunDB, run_id)
    if not row:
        raise HTTPException(status_code=404, detail='not_found')
    return row.payload
