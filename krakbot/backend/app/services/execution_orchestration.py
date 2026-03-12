from __future__ import annotations

from app.adapters.execution.hyperliquid_adapter import HyperliquidExecutionAdapter
from app.core.config import settings
from app.execution.gateway import VenueGateway
from app.execution.models import OrderIntent, VenueContext
from app.execution.orchestrator import ExecutionOrchestrator
from app.execution.venue_adapters import FreqtradeVenueAdapter
from app.services.live_trading_guard import enforce_live_trading_order_guard


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
    if selected_venue == 'hyperliquid':
        if not settings.hyperliquid_enabled:
            # Safe backward-compatible fallback for paper-order API when HL is disabled.
            selected_venue = 'paper'
        elif settings.hyperliquid_environment != 'testnet':
            # Mainnet requires explicit live trading guard enablement and caps.
            px_ref = float(limit_price or 0.0)
            if px_ref <= 0:
                px_ref = 1.0
            notional = abs(float(qty or 0.0) * px_ref)
            guard = enforce_live_trading_order_guard(
                db,
                strategy_instance_id=strategy_instance_id,
                notional_usd=notional,
            )
            if not guard.get('ok'):
                return {
                    'accepted': False,
                    'error_code': guard.get('error_code') or 'live_trading_guard_block',
                    'message': guard.get('message') or 'live trading blocked by guard policy',
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
