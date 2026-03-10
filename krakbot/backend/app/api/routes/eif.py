from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(prefix='/eif', tags=['eif'])


def _bounded(limit: int, max_limit: int = 200) -> int:
    return max(1, min(int(limit), max_limit))


def _guard_api_enabled() -> dict | None:
    if not settings.eif_analytics_api_enabled:
        return {"analytics_api_enabled": False, "items": [], "total": 0}
    return None


@router.get('/summary')
def eif_summary(db: Session = Depends(get_db)):
    guard = _guard_api_enabled()
    if guard is not None:
        return guard

    summary = db.execute(
        text(
            """
            SELECT
              (SELECT COUNT(*) FROM eif_trade_context_events) AS context_events,
              (SELECT COUNT(*) FROM eif_filter_decisions) AS filter_decisions,
              (SELECT COUNT(*) FROM eif_filter_decisions WHERE allowed = TRUE) AS allowed_decisions,
              (SELECT COUNT(*) FROM eif_filter_decisions WHERE allowed = FALSE) AS blocked_decisions,
              (SELECT COUNT(*) FROM eif_regime_snapshots) AS regime_snapshots,
              (SELECT COUNT(*) FROM eif_scorecard_snapshots) AS scorecard_snapshots
            """
        )
    ).mappings().first()
    return {
        "analytics_api_enabled": settings.eif_analytics_api_enabled,
        "capture_enabled": settings.eif_capture_enabled,
        "shadow_mode": settings.eif_filter_shadow_mode,
        "enforce_mode": settings.eif_filter_enforce_mode,
        "summary": dict(summary or {}),
    }


@router.get('/regimes')
def eif_regimes(
    market: str | None = None,
    strategy_instance_id: str | None = None,
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
):
    guard = _guard_api_enabled()
    if guard is not None:
        return guard

    limit = _bounded(limit)
    offset = max(0, int(offset))
    rows = db.execute(
        text(
            """
            SELECT id, strategy_instance_id, market, regime_version, trend, volatility, liquidity,
                   session_structure, sample_size, features, captured_ts
            FROM eif_regime_snapshots
            WHERE (:market IS NULL OR market = :market)
              AND (:sid IS NULL OR strategy_instance_id = :sid)
            ORDER BY captured_ts DESC, id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"market": market, "sid": strategy_instance_id, "limit": limit, "offset": offset},
    ).mappings().all()
    return {"analytics_api_enabled": True, "items": [dict(r) for r in rows], "limit": limit, "offset": offset}


@router.get('/filter-decisions')
def eif_filter_decisions(
    market: str | None = None,
    strategy_instance_id: str | None = None,
    reason_code: str | None = None,
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
):
    guard = _guard_api_enabled()
    if guard is not None:
        return guard

    limit = _bounded(limit)
    offset = max(0, int(offset))
    rows = db.execute(
        text(
            """
            SELECT id, strategy_instance_id, market, decision, reason_code, allowed,
                   precedence_stage, shadow_mode, enforce_mode, filter_engine_version,
                   trace, details, ts
            FROM eif_filter_decisions
            WHERE (:market IS NULL OR market = :market)
              AND (:sid IS NULL OR strategy_instance_id = :sid)
              AND (:reason_code IS NULL OR reason_code = :reason_code)
            ORDER BY ts DESC, id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {
            "market": market,
            "sid": strategy_instance_id,
            "reason_code": reason_code,
            "limit": limit,
            "offset": offset,
        },
    ).mappings().all()

    reason_rows = db.execute(
        text(
            """
            SELECT reason_code, COUNT(*)::int AS count
            FROM eif_filter_decisions
            WHERE (:market IS NULL OR market = :market)
              AND (:sid IS NULL OR strategy_instance_id = :sid)
            GROUP BY reason_code
            ORDER BY count DESC, reason_code ASC
            LIMIT 20
            """
        ),
        {"market": market, "sid": strategy_instance_id},
    ).mappings().all()

    return {
        "analytics_api_enabled": True,
        "items": [dict(r) for r in rows],
        "reason_breakdown": [dict(r) for r in reason_rows],
        "limit": limit,
        "offset": offset,
    }


@router.get('/scorecards')
def eif_scorecards(
    strategy_instance_id: str | None = None,
    market: str | None = None,
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
):
    guard = _guard_api_enabled()
    if guard is not None:
        return guard

    limit = _bounded(limit)
    offset = max(0, int(offset))
    rows = db.execute(
        text(
            """
            SELECT id, strategy_instance_id, market, snapshot_type, window_label,
                   win_rate, expectancy, pnl_per_trade, sample_size, payload, ts
            FROM eif_scorecard_snapshots
            WHERE (:sid IS NULL OR strategy_instance_id = :sid)
              AND (:market IS NULL OR market = :market)
            ORDER BY ts DESC, id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"sid": strategy_instance_id, "market": market, "limit": limit, "offset": offset},
    ).mappings().all()
    return {"analytics_api_enabled": True, "items": [dict(r) for r in rows], "limit": limit, "offset": offset}


@router.get('/trade-trace')
def eif_trade_trace(
    strategy_instance_id: str | None = None,
    market: str | None = None,
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
):
    guard = _guard_api_enabled()
    if guard is not None:
        return guard

    limit = _bounded(limit)
    offset = max(0, int(offset))
    rows = db.execute(
        text(
            """
            SELECT id, strategy_instance_id, market, event_type, side, qty, price, pnl_usd, tags, context, ts
            FROM eif_trade_context_events
            WHERE (:sid IS NULL OR strategy_instance_id = :sid)
              AND (:market IS NULL OR market = :market)
            ORDER BY ts DESC, id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"sid": strategy_instance_id, "market": market, "limit": limit, "offset": offset},
    ).mappings().all()
    return {"analytics_api_enabled": True, "items": [dict(r) for r in rows], "limit": limit, "offset": offset}


@router.get('/events/recent')
def eif_recent_events(limit: int = Query(default=50), db: Session = Depends(get_db)):
    limit = _bounded(limit, max_limit=500)
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
