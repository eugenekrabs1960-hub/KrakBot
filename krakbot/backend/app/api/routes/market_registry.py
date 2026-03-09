from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.market_registry import MarketRegistryCreate, MarketToggle
from app.services.market_registry import list_markets, create_market, toggle_market, assign_market

router = APIRouter(prefix='/markets', tags=['market-registry'])


@router.get('')
def markets(enabled_only: bool = False, db: Session = Depends(get_db)):
    return {'items': list_markets(db, enabled_only=enabled_only)}


@router.post('')
def market_create(payload: MarketRegistryCreate, db: Session = Depends(get_db)):
    return {'ok': True, **create_market(db, payload.model_dump())}


@router.post('/{market_id}/toggle')
def market_toggle(market_id: str, payload: MarketToggle, db: Session = Depends(get_db)):
    toggle_market(db, market_id=market_id, enabled=payload.enabled)
    return {'ok': True, 'market_id': market_id, 'enabled': payload.enabled}


@router.post('/assign')
def market_assign(strategy_instance_id: str, market_id: str, enabled: bool = True, db: Session = Depends(get_db)):
    assign_market(db, strategy_instance_id=strategy_instance_id, market_id=market_id, enabled=enabled)
    return {'ok': True, 'strategy_instance_id': strategy_instance_id, 'market_id': market_id, 'enabled': enabled}
