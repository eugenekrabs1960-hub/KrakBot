from app.adapters.execution.hyperliquid_adapter import HyperliquidExecutionAdapter
from app.execution.models import OrderIntent, VenueContext


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_submit_order_success_with_mocked_exchange(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'hyperliquid_enabled', True, raising=False)

    def fake_post(url, json, timeout=20):
        assert url.endswith('/exchange')
        assert 'action' in json
        return _Resp({'response': {'data': {'statuses': [{'resting': {'oid': 12345}}]}}})

    adapter = HyperliquidExecutionAdapter(
        signer=lambda _a: {'r': 'sig'},
        post=fake_post,
    )

    out = adapter.submit_order(
        OrderIntent(
            strategy_instance_id='inst_1',
            market='SOL-PERP',
            side='buy',
            qty=0.5,
            order_type='limit',
            limit_price=123.4,
            venue_context=VenueContext(venue='hyperliquid', environment='testnet'),
        )
    )

    assert out.accepted is True
    assert out.order_state is not None
    assert out.order_state.order_id == '12345'


def test_fetch_account_and_positions_from_info(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'hyperliquid_enabled', True, raising=False)
    monkeypatch.setattr(settings, 'hyperliquid_account_address', '0xabc', raising=False)

    payload = {
        'marginSummary': {'accountValue': '12000.5', 'withdrawable': '9000', 'totalMarginUsed': '1200'},
        'assetPositions': [
            {
                'position': {
                    'coin': 'SOL',
                    'szi': '2.5',
                    'entryPx': '110.0',
                    'realizedPnl': '15.2',
                    'unrealizedPnl': '3.1',
                    'liquidationPx': '70.0',
                    'leverage': {'value': '5'},
                }
            }
        ],
    }

    def fake_post(url, json, timeout=20):
        assert url.endswith('/info')
        return _Resp(payload)

    adapter = HyperliquidExecutionAdapter(post=fake_post)
    account = adapter.fetch_account_state()
    positions = adapter.fetch_positions()

    assert account is not None
    assert account.equity_usd == 12000.5
    assert len(positions) == 1
    assert positions[0].market == 'SOL-PERP'
    assert positions[0].leverage == 5.0
