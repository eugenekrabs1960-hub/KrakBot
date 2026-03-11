from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.model_lab import latest_model, strategy_benchmarks, train_baseline

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
