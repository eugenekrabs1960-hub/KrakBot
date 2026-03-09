import random

from sqlalchemy.orm import Session

from app.adapters.execution.base import ExecutionEngine, OrderIntent
from app.adapters.execution.freqtrade_bridge import FreqtradeBridge
from app.services.execution_store import create_order, create_execution
from app.services.portfolio_engine import apply_fill
from app.services.performance_snapshot import recompute_strategy_snapshot


class FreqtradeExecutionAdapter(ExecutionEngine):
    """
    Phase 3 adapter: canonical persistence + optional real Freqtrade bridge + portfolio/metrics updates.
    """

    def __init__(self, db: Session):
        self.db = db
        self.bridge = FreqtradeBridge()

    def submit_order(self, intent: OrderIntent) -> dict:
        order = create_order(self.db, intent, engine='freqtrade')

        bridge_resp = self.bridge.place_order(
            pair=intent.market,
            side=intent.side,
            amount=intent.qty,
            order_type=intent.order_type,
            price=intent.limit_price,
        )

        # MVP fallback: simulated paper fill if bridge unavailable
        fill_price = intent.limit_price or round(random.uniform(100.0, 220.0), 4)
        if bridge_resp:
            # Best-effort extraction from Freqtrade response.
            fill_price = float(
                bridge_resp.get('price')
                or bridge_resp.get('open_rate')
                or bridge_resp.get('rate')
                or fill_price
            )

        exe = create_execution(
            self.db,
            order_id=order['order_id'],
            strategy_instance_id=intent.strategy_instance_id,
            market=intent.market,
            side=intent.side,
            qty=intent.qty,
            fill_price=fill_price,
            engine='freqtrade',
            engine_trade_id=(bridge_resp or {}).get('id') if isinstance(bridge_resp, dict) else f"ft_{order['order_id']}",
        )

        portfolio = apply_fill(
            self.db,
            strategy_instance_id=intent.strategy_instance_id,
            market=intent.market,
            side=intent.side,
            qty=intent.qty,
            fill_price=fill_price,
        )
        recompute_strategy_snapshot(self.db, intent.strategy_instance_id)

        return {
            'accepted': True,
            'engine': 'freqtrade',
            'bridge_used': bool(bridge_resp),
            **order,
            **exe,
            'fill_price': fill_price,
            'portfolio': portfolio,
        }

    def cancel_order(self, order_id: str) -> dict:
        return {'cancelled': False, 'order_id': order_id, 'reason': 'already-filled-in-paper-sim'}

    def fetch_open_orders(self) -> list[dict]:
        return []

    def fetch_fills(self, since_ts: str | None = None) -> list[dict]:
        return []

    def health(self) -> dict:
        return {'engine': 'freqtrade', 'ok': True, 'bridge_enabled': self.bridge.enabled}
