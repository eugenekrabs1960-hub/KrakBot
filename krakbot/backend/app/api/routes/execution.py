import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.adapters.execution.hyperliquid_adapter import HyperliquidExecutionAdapter
from app.core.config import settings
from app.db.session import get_db
from app.services.hyperliquid_reconciliation import HyperliquidReconciliationService
from app.services.checkpoints import load_checkpoint
from app.services.hyperliquid_market_data import HyperliquidMarketDataService, list_latest_training_features
from app.services.hyperliquid_market_scheduler import hyperliquid_market_scheduler
from app.services.hyperliquid_dataset_jobs import build_labeled_dataset_v1, export_training_dataset_csv
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


@router.post('/hyperliquid/collect-market-data')
def hyperliquid_collect_market_data(symbols_limit: int = 120, db: Session = Depends(get_db)):
    svc = HyperliquidMarketDataService(environment=settings.hyperliquid_environment)
    out = svc.collect_once(db, symbols_limit=symbols_limit)
    return out.__dict__


@router.post('/hyperliquid/collector/run-once')
def hyperliquid_collector_run_once():
    return hyperliquid_market_scheduler.run_once()


@router.get('/hyperliquid/collector/status')
def hyperliquid_collector_status(db: Session = Depends(get_db)):
    checkpoint = load_checkpoint(db, 'hyperliquid_market_collector')
    return {'ok': True, 'enabled': settings.hyperliquid_market_collector_enabled, 'checkpoint': checkpoint}


@router.get('/hyperliquid/training-features')
def hyperliquid_training_features(limit: int = 200, symbol: str | None = None, db: Session = Depends(get_db)):
    return {'ok': True, 'items': list_latest_training_features(db, limit=limit, symbol=symbol)}


@router.get('/hyperliquid/training-features/export')
def hyperliquid_training_features_export(limit: int = 1000, symbol: str | None = None, db: Session = Depends(get_db)):
    rows = list_latest_training_features(db, limit=limit, symbol=symbol)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['id', 'ts', 'environment', 'symbol', 'mid_price', 'ret_1', 'ret_5', 'ret_15', 'source'])
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k) for k in writer.fieldnames})
    return PlainTextResponse(output.getvalue(), media_type='text/csv')


@router.post('/hyperliquid/training-features/export-job')
def hyperliquid_training_features_export_job(
    symbol: str | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    limit: int = 20000,
    db: Session = Depends(get_db),
):
    try:
        return export_training_dataset_csv(db, symbol=symbol, from_ts=from_ts, to_ts=to_ts, limit=limit)
    except Exception as exc:
        return {'ok': False, 'error': str(exc)[:300]}


@router.post('/hyperliquid/training-features/build-labeled-v1')
def hyperliquid_training_features_build_labeled_v1(
    symbol: str,
    from_ts: int | None = None,
    to_ts: int | None = None,
    limit: int = 50000,
    db: Session = Depends(get_db),
):
    try:
        return build_labeled_dataset_v1(db, symbol=symbol, from_ts=from_ts, to_ts=to_ts, limit=limit)
    except Exception as exc:
        return {'ok': False, 'error': str(exc)[:300]}
