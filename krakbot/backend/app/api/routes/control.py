from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.control import BotCommand, StrategyToggle
from app.services.orchestrator import OrchestratorService
from app.services.strategy_registry import set_enabled

router = APIRouter(prefix='/control', tags=['control'])


@router.post('/bot')
def bot_command(payload: BotCommand, db: Session = Depends(get_db)):
    svc = OrchestratorService()
    try:
        state = svc.apply_command(db, payload.command)
        return {'accepted': True, 'state': state, 'command': payload.command}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get('/bot')
def bot_state(db: Session = Depends(get_db)):
    svc = OrchestratorService()
    return {'state': svc.get_state(db)}


@router.post('/strategy/toggle')
def toggle_strategy(payload: StrategyToggle, db: Session = Depends(get_db)):
    set_enabled(db, payload.strategy_instance_id, payload.enabled)
    return {'ok': True, 'strategy_instance_id': payload.strategy_instance_id, 'enabled': payload.enabled}
