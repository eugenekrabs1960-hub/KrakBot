from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.adapters.execution.hyperliquid_adapter import HyperliquidExecutionAdapter
from app.core.config import settings
from app.db.session import get_db
from app.services.hyperliquid_reconciliation import HyperliquidReconciliationService
from app.services.hyperliquid_state_store import (
    compute_latest_hyperliquid_risk_snapshot,
    list_latest_hyperliquid_account_snapshots,
    list_latest_hyperliquid_position_snapshots,
)

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


@router.post('/hyperliquid/reconcile')
def hyperliquid_reconcile(db: Session = Depends(get_db)):
    svc = HyperliquidReconciliationService(
        adapter=HyperliquidExecutionAdapter(environment=settings.hyperliquid_environment)
    )
    return svc.run_once(db)


@router.get('/hyperliquid/reconcile/history')
def hyperliquid_reconcile_history(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            """
            SELECT id, kind, status, details, ts
            FROM reconciliations
            WHERE kind='hyperliquid_state'
            ORDER BY id DESC
            LIMIT :limit
            """
        ),
        {'limit': max(1, min(200, int(limit)))},
    ).mappings().all()
    return {'ok': True, 'items': [dict(r) for r in rows]}


@router.get('/hyperliquid/snapshots/account')
def hyperliquid_account_snapshots(limit: int = 20, db: Session = Depends(get_db)):
    return {'ok': True, 'items': list_latest_hyperliquid_account_snapshots(db, limit=limit)}


@router.get('/hyperliquid/snapshots/positions')
def hyperliquid_position_snapshots(limit: int = 50, db: Session = Depends(get_db)):
    return {'ok': True, 'items': list_latest_hyperliquid_position_snapshots(db, limit=limit)}


@router.get('/hyperliquid/risk-snapshot')
def hyperliquid_risk_snapshot(db: Session = Depends(get_db)):
    return compute_latest_hyperliquid_risk_snapshot(db)
