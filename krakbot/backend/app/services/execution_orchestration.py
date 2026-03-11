from __future__ import annotations

from app.execution.gateway import VenueGateway
from app.execution.models import OrderIntent, VenueContext
from app.execution.orchestrator import ExecutionOrchestrator
from app.execution.venue_adapters import FreqtradeVenueAdapter


def execute_paper_order(db, *, strategy_instance_id: str, market: str, side: str, qty: float, order_type: str, limit_price: float | None):
    gateway = VenueGateway()
    gateway.register('paper', FreqtradeVenueAdapter(db))

    orchestrator = ExecutionOrchestrator(gateway=gateway)
    report = orchestrator.execute_intent(
        OrderIntent(
            strategy_instance_id=strategy_instance_id,
            market=market,
            side='buy' if side.lower() == 'buy' else 'sell',
            qty=qty,
            order_type='limit' if order_type == 'limit' else 'market',
            limit_price=limit_price,
            venue_context=VenueContext(venue='paper', environment='testnet'),
        )
    )

    legacy = report.venue_payload.get('legacy_result') if isinstance(report.venue_payload, dict) else None
    if isinstance(legacy, dict):
        return legacy
    if report.accepted:
        return {'accepted': True}
    return {
        'accepted': False,
        'error_code': report.error_code or 'execution_failed',
        'message': report.message or 'execution failed',
        'market': market,
    }
