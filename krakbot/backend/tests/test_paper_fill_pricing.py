from app.adapters.execution.base import OrderIntent
from app.adapters.execution.freqtrade_adapter import FreqtradeExecutionAdapter


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _FakeDB:
    def __init__(self, latest_price=None):
        self.latest_price = latest_price

    def execute(self, *_args, **_kwargs):
        row = None if self.latest_price is None else {'price': self.latest_price}
        return _FakeResult(row)


def test_success_uses_latest_market_trade_price_exactly(monkeypatch):
    db = _FakeDB(latest_price=321.1234)
    adapter = FreqtradeExecutionAdapter(db)

    captured = {}

    monkeypatch.setattr(adapter.bridge, 'place_order', lambda **_k: {'id': 'bridge-1', 'price': 99999.0})
    monkeypatch.setattr('app.adapters.execution.freqtrade_adapter.create_order', lambda *_a, **_k: {'order_id': 'ord_1'})

    def _create_execution(_db, **kwargs):
        captured['fill_price'] = kwargs['fill_price']
        return {'execution_id': 'exe_1'}

    monkeypatch.setattr('app.adapters.execution.freqtrade_adapter.create_execution', _create_execution)
    monkeypatch.setattr('app.adapters.execution.freqtrade_adapter.apply_fill', lambda *_a, **_k: {'equity_usd': 10000})
    monkeypatch.setattr('app.adapters.execution.freqtrade_adapter.recompute_strategy_snapshot', lambda *_a, **_k: None)

    result = adapter.submit_order(
        OrderIntent(
            strategy_instance_id='inst_1',
            market='SOL/USD',
            side='buy',
            qty=0.1,
            order_type='limit',
            limit_price=100.0,
        )
    )

    assert result['accepted'] is True
    assert result['fill_price'] == 321.1234
    assert captured['fill_price'] == 321.1234


def test_failure_when_no_market_trade_price_exists(monkeypatch):
    db = _FakeDB(latest_price=None)
    adapter = FreqtradeExecutionAdapter(db)

    called = {'create_execution': False, 'apply_fill': False, 'create_order': False}

    monkeypatch.setattr(adapter.bridge, 'place_order', lambda **_k: {'id': 'bridge-1'})

    def _mark_order(*_a, **_k):
        called['create_order'] = True
        return {'order_id': 'ord_1'}

    def _mark_exec(*_a, **_k):
        called['create_execution'] = True
        return {'execution_id': 'exe_1'}

    def _mark_fill(*_a, **_k):
        called['apply_fill'] = True
        return {'equity_usd': 10000}

    monkeypatch.setattr('app.adapters.execution.freqtrade_adapter.create_order', _mark_order)
    monkeypatch.setattr('app.adapters.execution.freqtrade_adapter.create_execution', _mark_exec)
    monkeypatch.setattr('app.adapters.execution.freqtrade_adapter.apply_fill', _mark_fill)
    monkeypatch.setattr('app.adapters.execution.freqtrade_adapter.recompute_strategy_snapshot', lambda *_a, **_k: None)

    result = adapter.submit_order(
        OrderIntent(
            strategy_instance_id='inst_1',
            market='SOL/USD',
            side='buy',
            qty=0.1,
            order_type='market',
        )
    )

    assert result == {
        'accepted': False,
        'error_code': 'no_market_trade_price',
        'message': 'No market trade price available for fill',
        'market': 'SOL/USD',
    }
    assert called['create_order'] is False
    assert called['create_execution'] is False
    assert called['apply_fill'] is False


def test_replay_returns_identical_response_for_failure_shape():
    # Deterministic failure payload shape for idempotent storage/replay.
    db = _FakeDB(latest_price=None)
    adapter = FreqtradeExecutionAdapter(db)

    payload = OrderIntent(strategy_instance_id='inst_1', market='SOL/USD', side='sell', qty=0.3)
    first = adapter.submit_order(payload)
    second = adapter.submit_order(payload)

    assert first == second
