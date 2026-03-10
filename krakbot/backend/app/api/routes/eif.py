from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(prefix='/eif', tags=['eif'])


@router.get('/summary')
def eif_summary(db: Session = Depends(get_db)):
    if not settings.eif_capture_enabled:
        return {"capture_enabled": False, "scorecard_compute_enabled": settings.eif_scorecard_compute_enabled, "summary": {}}

    summary = db.execute(
        text(
            """
            SELECT
              (SELECT COUNT(*) FROM eif_trade_context_events) AS context_events,
              (SELECT COUNT(*) FROM eif_filter_decisions) AS filter_decisions,
              (SELECT COUNT(*) FROM eif_regime_snapshots) AS regime_snapshots,
              (SELECT COUNT(*) FROM eif_scorecard_snapshots) AS scorecard_snapshots
            """
        )
    ).mappings().first()
    return {
        "capture_enabled": settings.eif_capture_enabled,
        "scorecard_compute_enabled": settings.eif_scorecard_compute_enabled,
        "summary": dict(summary or {}),
    }


@router.get('/events/recent')
def eif_recent_events(limit: int = Query(default=50), db: Session = Depends(get_db)):
    limit = max(1, min(int(limit), 500))
    rows = db.execute(
        text(
            """
            SELECT strategy_instance_id, market, event_type, side, qty, price, pnl_usd, ts
            FROM eif_trade_context_events
            ORDER BY ts DESC, id DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()
    return {"items": [dict(r) for r in rows], "limit": limit}
