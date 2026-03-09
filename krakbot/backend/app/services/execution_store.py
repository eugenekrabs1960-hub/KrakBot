import time
import uuid
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.adapters.execution.base import OrderIntent


def create_order(db: Session, intent: OrderIntent, engine: str) -> dict:
    order_id = f"ord_{uuid.uuid4().hex[:12]}"
    db.execute(
        text(
            """
            INSERT INTO orders(id, strategy_instance_id, venue, market, instrument_type, side, order_type, qty, limit_price, status, engine)
            VALUES (:id, :strategy_instance_id, 'kraken', :market, 'spot', :side, :order_type, :qty, :limit_price, 'accepted', :engine)
            """
        ),
        {
            'id': order_id,
            'strategy_instance_id': intent.strategy_instance_id,
            'market': intent.market,
            'side': intent.side,
            'order_type': intent.order_type,
            'qty': intent.qty,
            'limit_price': intent.limit_price,
            'engine': engine,
        },
    )
    db.commit()
    return {'order_id': order_id}


def create_execution(db: Session, order_id: str, strategy_instance_id: str, market: str, side: str, qty: float, fill_price: float, engine: str, engine_trade_id: str | None = None):
    exec_id = f"exe_{uuid.uuid4().hex[:12]}"
    db.execute(
        text(
            """
            INSERT INTO executions(id, order_id, strategy_instance_id, venue, market, side, fill_price, fill_qty, fee_usd, realized_pnl_usd, engine, engine_trade_id, event_ts)
            VALUES (:id, :order_id, :strategy_instance_id, 'kraken', :market, :side, :fill_price, :fill_qty, 0, NULL, :engine, :engine_trade_id, :event_ts)
            """
        ),
        {
            'id': exec_id,
            'order_id': order_id,
            'strategy_instance_id': strategy_instance_id,
            'market': market,
            'side': side,
            'fill_price': fill_price,
            'fill_qty': qty,
            'engine': engine,
            'engine_trade_id': engine_trade_id,
            'event_ts': int(time.time() * 1000),
        },
    )
    db.execute(
        text("UPDATE orders SET status='filled', updated_at=NOW() WHERE id=:id"),
        {'id': order_id},
    )
    db.commit()
    return {'execution_id': exec_id}
