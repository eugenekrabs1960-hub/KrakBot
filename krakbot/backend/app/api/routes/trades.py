from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.adapters.execution.base import OrderIntent
from app.adapters.execution.freqtrade_adapter import FreqtradeExecutionAdapter
from app.db.session import get_db
from app.schemas.trade import PaperOrderRequest
from app.services.idempotency import check_or_store, update_response

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

    adapter = FreqtradeExecutionAdapter(db)
    result = adapter.submit_order(
        OrderIntent(
            strategy_instance_id=payload.strategy_instance_id,
            market=payload.market,
            side='buy' if payload.side.lower() == 'buy' else 'sell',
            qty=payload.qty,
            order_type='limit' if payload.order_type == 'limit' else 'market',
            limit_price=payload.limit_price,
        )
    )
    update_response(db, x_idempotency_key, result)
    return result
