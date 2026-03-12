from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.control import (
    BotCommand,
    StrategyToggle,
    ExecutionVenueUpdate,
    LiveTradingDisableRequest,
    LiveTradingEnableRequest,
)
from app.services.orchestrator import OrchestratorService
from app.services.strategy_registry import set_enabled
from app.services.execution_preferences import get_default_execution_venue, set_default_execution_venue
from app.core.config import settings
from app.services.live_trading_guard import (
    disable_live_trading_guard,
    enable_live_trading_guard,
    get_live_trading_guard,
)

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


@router.get('/execution/venue')
def get_execution_venue(db: Session = Depends(get_db)):
    return {'default_venue': get_default_execution_venue(db)}


@router.post('/execution/venue')
def set_execution_venue(payload: ExecutionVenueUpdate, db: Session = Depends(get_db)):
    venue = set_default_execution_venue(db, payload.default_venue)
    return {'ok': True, 'default_venue': venue}


@router.get('/live-paper-test-mode')
def live_paper_test_mode_config():
    return {
        'enabled': settings.live_paper_test_mode_enabled,
        'market': settings.live_paper_test_market,
        'loop_interval_sec': settings.live_paper_test_loop_interval_sec,
        'order_qty': settings.live_paper_test_order_qty,
        'max_orders_per_minute': settings.live_paper_test_max_orders_per_minute,
        'min_seconds_between_orders': settings.live_paper_test_min_seconds_between_orders,
        'force_paper_only': settings.live_paper_test_force_paper_only,
    }


@router.get('/eif-flags')
def eif_flags():
    return {
        'eif': {
            'capture': {'enabled': settings.eif_capture_enabled},
            'scorecard': {'compute': {'enabled': settings.eif_scorecard_compute_enabled}},
            'filter': {
                'shadow_mode': settings.eif_filter_shadow_mode,
                'enforce_mode': settings.eif_filter_enforce_mode,
                'fail_closed': settings.eif_filter_fail_closed,
            },
            'analytics': {'api': {'enabled': settings.eif_analytics_api_enabled}},
        }
    }


@router.get('/live-trading')
def get_live_trading_guard_state(db: Session = Depends(get_db)):
    return get_live_trading_guard(db)


@router.post('/live-trading/enable')
def enable_live_trading(payload: LiveTradingEnableRequest, db: Session = Depends(get_db)):
    return enable_live_trading_guard(
        db,
        confirm_phrase=payload.confirm_phrase,
        max_notional_usd_per_order=payload.max_notional_usd_per_order,
        max_daily_loss_usd=payload.max_daily_loss_usd,
        allowed_agents=payload.allowed_agents,
    )


@router.post('/live-trading/disable')
def disable_live_trading(payload: LiveTradingDisableRequest, db: Session = Depends(get_db)):
    return disable_live_trading_guard(db, confirm_phrase=payload.confirm_phrase)
