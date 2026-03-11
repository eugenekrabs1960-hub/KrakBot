from __future__ import annotations

from app.adapters.execution.hyperliquid_adapter import HyperliquidExecutionAdapter
from app.core.config import settings
from app.execution.gateway import VenueGateway
from app.execution.models import OrderIntent, VenueContext
from app.execution.orchestrator import ExecutionOrchestrator
from app.execution.venue_adapters import FreqtradeVenueAdapter


def execute_paper_order(
    db,
    *,
    strategy_instance_id: str,
    market: str,
    side: str,
    qty: float,
    order_type: str,
    limit_price: float | None,
    venue: str = 'paper',
):
    gateway = VenueGateway()
    gateway.register('paper', FreqtradeVenueAdapter(db))
    gateway.register('hyperliquid', HyperliquidExecutionAdapter(environment=settings.hyperliquid_environment))

    selected_venue = (venue or 'paper').lower()
    if selected_venue == 'hyperliquid' and settings.hyperliquid_environment != 'testnet':
        return {
            'accepted': False,
            'error_code': 'unsafe_environment',
            'message': 'hyperliquid live execution is blocked unless environment is testnet',
            'market': market,
        }

    orchestrator = ExecutionOrchestrator(gateway=gateway)
    try:
        report = orchestrator.execute_intent(
            OrderIntent(
                strategy_instance_id=strategy_instance_id,
                market=market,
                side='buy' if side.lower() == 'buy' else 'sell',
                qty=qty,
                order_type='limit' if order_type == 'limit' else 'market',
                limit_price=limit_price,
                venue_context=VenueContext(venue=selected_venue, environment='testnet'),
            )
        )
    except KeyError:
        return {
            'accepted': False,
            'error_code': 'unknown_venue',
            'message': f'unsupported venue: {selected_venue}',
            'market': market,
        }

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
