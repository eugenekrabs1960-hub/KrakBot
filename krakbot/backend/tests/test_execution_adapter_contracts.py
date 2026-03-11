from app.adapters.execution.hyperliquid_adapter import HyperliquidExecutionAdapter
from app.execution.models import OrderIntent, VenueContext


def _assert_adapter_contract(adapter):
    health = adapter.health()
    assert isinstance(health, dict)
    assert 'ok' in health

    cancel = adapter.cancel_order('ord_x')
    assert isinstance(cancel, dict)

    positions = adapter.fetch_positions()
    assert isinstance(positions, list)


def test_hyperliquid_adapter_phase_a_contract_shape():
    adapter = HyperliquidExecutionAdapter(environment='testnet')
    _assert_adapter_contract(adapter)

    out = adapter.submit_order(
        OrderIntent(
            strategy_instance_id='inst_1',
            market='SOL-PERP',
            side='buy',
            qty=1.0,
            venue_context=VenueContext(venue='hyperliquid', environment='testnet'),
        )
    )
    assert out.accepted is False
    assert out.error_code in {'venue_disabled', 'auth_not_configured'}
