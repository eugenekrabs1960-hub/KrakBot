import random

from sqlalchemy.orm import Session

from app.adapters.execution.base import ExecutionEngine, OrderIntent
from app.services.execution_store import create_order, create_execution


class FreqtradeExecutionAdapter(ExecutionEngine):
    """
    Phase 2 adapter: normalized canonical order/fill persistence with paper-fill simulation.
    Replace simulated fill path with real Freqtrade bridge in Phase 3.
    """

    def __init__(self, db: Session):
        self.db = db

    def submit_order(self, intent: OrderIntent) -> dict:
        order = create_order(self.db, intent, engine='freqtrade')
        fill_price = intent.limit_price or round(random.uniform(100.0, 220.0), 4)
        exe = create_execution(
            self.db,
            order_id=order['order_id'],
            strategy_instance_id=intent.strategy_instance_id,
            market=intent.market,
            side=intent.side,
            qty=intent.qty,
            fill_price=fill_price,
            engine='freqtrade',
            engine_trade_id=f"ft_{order['order_id']}",
        )
        return {'accepted': True, 'engine': 'freqtrade', **order, **exe, 'fill_price': fill_price}

    def cancel_order(self, order_id: str) -> dict:
        return {'cancelled': False, 'order_id': order_id, 'reason': 'already-filled-in-paper-sim'}

    def fetch_open_orders(self) -> list[dict]:
        return []

    def fetch_fills(self, since_ts: str | None = None) -> list[dict]:
        return []

    def health(self) -> dict:
        return {'engine': 'freqtrade', 'ok': True, 'mode': 'paper-sim'}
