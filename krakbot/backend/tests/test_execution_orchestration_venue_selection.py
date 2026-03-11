from app.services.execution_orchestration import execute_paper_order


def test_unknown_venue_returns_error():
    out = execute_paper_order(
        db=None,
        strategy_instance_id='inst_1',
        market='SOL/USD',
        side='buy',
        qty=0.1,
        order_type='market',
        limit_price=None,
        venue='unknownx',
    )
    assert out['accepted'] is False
    assert out['error_code'] == 'unknown_venue'


def test_hyperliquid_mainnet_block_guard(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'hyperliquid_environment', 'mainnet', raising=False)

    out = execute_paper_order(
        db=None,
        strategy_instance_id='inst_1',
        market='SOL-PERP',
        side='buy',
        qty=0.1,
        order_type='market',
        limit_price=None,
        venue='hyperliquid',
    )
    assert out['accepted'] is False
    assert out['error_code'] == 'unsafe_environment'
