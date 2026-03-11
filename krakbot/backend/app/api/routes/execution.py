from fastapi import APIRouter

from app.adapters.execution.hyperliquid_adapter import HyperliquidExecutionAdapter
from app.core.config import settings

router = APIRouter(prefix='/execution', tags=['execution'])


@router.get('/hyperliquid/health')
def hyperliquid_health():
    adapter = HyperliquidExecutionAdapter(environment=settings.hyperliquid_environment)
    return {'ok': True, 'item': adapter.health()}


@router.get('/hyperliquid/account')
def hyperliquid_account():
    adapter = HyperliquidExecutionAdapter(environment=settings.hyperliquid_environment)
    account = adapter.fetch_account_state()
    return {'ok': True, 'item': account.__dict__ if account else None}


@router.get('/hyperliquid/positions')
def hyperliquid_positions():
    adapter = HyperliquidExecutionAdapter(environment=settings.hyperliquid_environment)
    positions = adapter.fetch_positions()
    return {'ok': True, 'items': [p.__dict__ for p in positions]}
