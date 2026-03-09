from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.strategy import StrategyInstanceCreate
from app.services.strategy_registry import create_instance

router = APIRouter(prefix='/strategies', tags=['strategies'])


@router.post('/instances')
def create_strategy_instance(payload: StrategyInstanceCreate, db: Session = Depends(get_db)):
    created = create_instance(
        db=db,
        strategy_name=payload.strategy_name,
        market=payload.market,
        instrument_type=payload.instrument_type,
        starting_equity_usd=payload.starting_equity_usd,
        params=payload.params,
    )
    return {'ok': True, **created}


@router.get('')
def list_strategies(db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            """
            SELECT si.id as strategy_instance_id,
                   s.name,
                   si.enabled,
                   si.status,
                   si.market,
                   COALESCE(ps.pnl_usd, 0) as pnl_usd,
                   COALESCE(ps.drawdown_pct, 0) as drawdown_pct,
                   COALESCE(ps.win_rate_pct, 0) as win_rate_pct,
                   COALESCE(ps.trade_count, 0) as trade_count
            FROM strategy_instances si
            JOIN strategies s ON s.id = si.strategy_id
            LEFT JOIN LATERAL (
                SELECT pnl_usd, drawdown_pct, win_rate_pct, trade_count
                FROM performance_snapshots p
                WHERE p.strategy_instance_id = si.id
                ORDER BY p.ts DESC
                LIMIT 1
            ) ps ON TRUE
            ORDER BY si.created_at DESC
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]
