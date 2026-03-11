from __future__ import annotations

from app.execution.models import AccountState, ExecutionReport, OrderIntent, PositionState


class HyperliquidExecutionAdapter:
    """Phase-A skeleton adapter for future native Hyperliquid execution path."""

    name = 'hyperliquid'

    def __init__(self, environment: str = 'testnet'):
        self.environment = environment

    def submit_order(self, intent: OrderIntent) -> ExecutionReport:
        return ExecutionReport(
            accepted=False,
            error_code='not_implemented',
            message='hyperliquid native adapter not implemented yet',
            venue_payload={'environment': self.environment, 'intent_market': intent.market},
        )

    def cancel_order(self, order_id: str) -> dict:
        return {'ok': False, 'error_code': 'not_implemented', 'order_id': order_id, 'venue': self.name}

    def fetch_account_state(self) -> AccountState | None:
        return None

    def fetch_positions(self) -> list[PositionState]:
        return []

    def health(self) -> dict:
        return {'ok': True, 'adapter': self.name, 'environment': self.environment, 'implemented': False}
