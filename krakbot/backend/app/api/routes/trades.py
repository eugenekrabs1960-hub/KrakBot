from fastapi import APIRouter
from app.api.models import runtime_settings
from app.services.execution.broker_router import get_broker

router = APIRouter(tags=['trades'])


@router.get('/trades')
def trades():
    broker = get_broker(runtime_settings.mode.execution_mode)
    return {'items': broker.get_fills(), 'mode': runtime_settings.mode.execution_mode}
