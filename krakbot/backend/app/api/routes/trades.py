from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.trade import PaperOrderRequest
from app.services.eif_capture import eif_capture
from app.services.eif_scorecard import eif_scorecard
from app.services.idempotency import check_or_store, update_response
from app.services.execution_orchestration import execute_paper_order

router = APIRouter(prefix='/trades', tags=['trades'])


@router.get('')
def list_trades(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            """
            SELECT e.strategy_instance_id,
                   e.side,
                   e.fill_qty AS qty,
                   e.fill_price AS entry_price,
                   e.realized_pnl_usd,
                   e.event_ts::text AS ts
            FROM executions e
            ORDER BY e.event_ts DESC
            LIMIT :limit
            """
        ),
        {'limit': limit},
    ).mappings().all()
    return {'items': [dict(r) for r in rows], 'limit': limit}


@router.post('/paper-order')
def paper_order(
    payload: PaperOrderRequest,
    db: Session = Depends(get_db),
    x_idempotency_key: str | None = Header(default=None),
):
    if not x_idempotency_key:
        raise HTTPException(status_code=400, detail='missing x-idempotency-key header')

    payload_dict = payload.model_dump()
    try:
        check = check_or_store(db, key=x_idempotency_key, scope='paper-order', payload=payload_dict)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if check['replayed']:
        return check['response'] or {}

    side = 'buy' if payload.side.lower() == 'buy' else 'sell'
    result = execute_paper_order(
        db,
        strategy_instance_id=payload.strategy_instance_id,
        market=payload.market,
        side=side,
        qty=payload.qty,
        order_type=payload.order_type,
        limit_price=payload.limit_price,
    )

    event_type = 'entry' if side == 'buy' else 'exit'
    eif_capture.capture_trade_context_event(
        db,
        strategy_instance_id=payload.strategy_instance_id,
        market=payload.market,
        event_type=event_type if result.get('accepted') else 'skip',
        side=side,
        qty=payload.qty,
        price=float(result.get('fill_price')) if result.get('fill_price') is not None else None,
        pnl_usd=None,
        tags=['mode:paper', f'event:{event_type if result.get("accepted") else "skip"}', 'source:api_paper_order'],
        context={'result': result, 'order_type': payload.order_type},
    )
    eif_capture.capture_filter_decision(
        db,
        strategy_instance_id=payload.strategy_instance_id,
        market=payload.market,
        event_type='decision',
        decision=event_type,
        reason_code='ok' if result.get('accepted') else (result.get('error_code') or 'unknown'),
        allowed=bool(result.get('accepted')),
        tags=['mode:paper', 'event:decision', 'source:api_paper_order'],
        details={'order_type': payload.order_type},
    )
    if result.get('accepted'):
        eif_scorecard.compute_snapshot(db, payload.strategy_instance_id, payload.market)

    update_response(db, x_idempotency_key, result)
    return result
