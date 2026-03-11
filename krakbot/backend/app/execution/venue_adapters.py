from __future__ import annotations

from app.adapters.execution.base import OrderIntent as LegacyOrderIntent
from app.adapters.execution.freqtrade_adapter import FreqtradeExecutionAdapter
from app.execution.models import AccountState, ExecutionReport, FillEvent, OrderIntent, OrderState, PositionState


class FreqtradeVenueAdapter:
    name = 'freqtrade'

    def __init__(self, db):
        self.db = db
        self._engine = FreqtradeExecutionAdapter(db)

    def submit_order(self, intent: OrderIntent) -> ExecutionReport:
        legacy = self._engine.submit_order(
            LegacyOrderIntent(
                strategy_instance_id=intent.strategy_instance_id,
                market=intent.market,
                side=intent.side,
                qty=intent.qty,
                order_type=intent.order_type,
                limit_price=intent.limit_price,
            )
        )

        if not legacy.get('accepted'):
            return ExecutionReport(
                accepted=False,
                error_code=legacy.get('error_code'),
                message=legacy.get('message'),
                venue_payload={'legacy_result': legacy},
            )

        order_state = OrderState(
            order_id=legacy['order_id'],
            strategy_instance_id=intent.strategy_instance_id,
            venue='freqtrade',
            market=intent.market,
            side=intent.side,
            qty=float(intent.qty),
            status='filled',
            filled_qty=float(intent.qty),
            avg_fill_price=float(legacy.get('fill_price') or 0.0),
        )
        fill_event = FillEvent(
            execution_id=legacy['execution_id'],
            order_id=legacy['order_id'],
            strategy_instance_id=intent.strategy_instance_id,
            venue='freqtrade',
            market=intent.market,
            side=intent.side,
            qty=float(intent.qty),
            price=float(legacy.get('fill_price') or 0.0),
        )
        return ExecutionReport(
            accepted=True,
            order_state=order_state,
            fill_event=fill_event,
            venue_payload={'legacy_result': legacy},
        )

    def cancel_order(self, order_id: str) -> dict:
        return self._engine.cancel_order(order_id)

    def fetch_account_state(self) -> AccountState | None:
        return None

    def fetch_positions(self) -> list[PositionState]:
        return []

    def health(self) -> dict:
        return self._engine.health()
