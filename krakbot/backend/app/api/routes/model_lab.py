from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.model_lab import (
    get_active_execution_model,
    get_active_model_for_paper,
    latest_model,
    list_job_history,
    set_active_execution_model,
    set_active_model_for_paper,
    strategy_benchmarks,
    train_baseline,
)

router = APIRouter(prefix='/model-lab', tags=['model-lab'])


@router.post('/train-baseline')
def train_baseline_endpoint(symbol: str = 'BTC', limit: int = 50000, db: Session = Depends(get_db)):
    return train_baseline(db, symbol=symbol, limit=limit)


@router.get('/latest-model')
def latest_model_endpoint(symbol: str = 'BTC'):
    return latest_model(symbol=symbol)


@router.get('/strategy-benchmarks')
def strategy_benchmarks_endpoint(symbol: str = 'BTC', limit: int = 50000, db: Session = Depends(get_db)):
    return strategy_benchmarks(db, symbol=symbol, limit=limit)


@router.get('/job-history')
def model_job_history(limit: int = 50):
    return list_job_history(limit=limit)


@router.get('/active-paper-model')
def active_paper_model(db: Session = Depends(get_db)):
    return get_active_model_for_paper(db)


@router.post('/promote-to-paper')
def promote_to_paper(symbol: str, model_path: str, confirm_phrase: str, db: Session = Depends(get_db)):
    return set_active_model_for_paper(db, symbol=symbol, model_path=model_path, confirm_phrase=confirm_phrase)


@router.get('/active-execution-model')
def active_execution_model(db: Session = Depends(get_db)):
    return get_active_execution_model(db)


@router.post('/set-active-execution-model')
def switch_active_execution_model(agent_id: str, confirm_phrase: str, db: Session = Depends(get_db)):
    return set_active_execution_model(db, agent_id=agent_id, confirm_phrase=confirm_phrase)
