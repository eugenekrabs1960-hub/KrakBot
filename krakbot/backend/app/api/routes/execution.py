from fastapi import APIRouter
from app.api.models import runtime_settings
from app.core.config import settings
from app.services.execution.broker_router import get_broker

router = APIRouter(tags=['execution'])


@router.get('/execution/health')
def execution_health():
    return {
        "mode": runtime_settings.mode.execution_mode,
        "live_armed": runtime_settings.mode.live_armed,
        "relay_configured": bool(settings.hyperliquid_order_relay_url),
        "account_configured": bool(settings.hyperliquid_account_address),
    }


@router.post('/execution/flatten-all')
def flatten_all():
    broker = get_broker(runtime_settings.mode.execution_mode)
    return broker.flatten_all_positions()
