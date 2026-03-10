from sqlalchemy import text
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

    def _latest_market_trade_price(self, market: str) -> float | None:
        row = self.db.execute(
            text(
                """
                SELECT price
                FROM market_trades
                WHERE market = :market
                ORDER BY event_ts DESC, id DESC
                LIMIT 1
                """
            ),
            {'market': market},
        ).mappings().first()
        if not row:
            return None
        return float(row['price'])

    def submit_order(self, intent: OrderIntent) -> dict:
        fill_price = self._latest_market_trade_price(intent.market)
        if fill_price is None:
            return {
                'accepted': False,
                'error_code': 'no_market_trade_price',
                'message': 'No market trade price available for fill',
                'market': intent.market,
            }

        order = create_order(self.db, intent, engine='freqtrade')

        bridge_resp = self.bridge.place_order(
            pair=intent.market,
            side=intent.side,
            amount=intent.qty,
            order_type=intent.order_type,
            price=intent.limit_price,
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
