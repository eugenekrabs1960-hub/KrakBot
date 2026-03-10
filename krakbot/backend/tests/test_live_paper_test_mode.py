import asyncio

from app.core.config import settings
from app.services.live_paper_test_mode import LivePaperTestModeService


class _FakeDB:
    def close(self):
        pass


def test_live_paper_test_mode_disabled_by_default():
    assert settings.live_paper_test_mode_enabled is False


def test_no_auto_orders_when_bot_not_running(monkeypatch):
    svc = LivePaperTestModeService()

    monkeypatch.setattr('app.services.live_paper_test_mode.SessionLocal', lambda: _FakeDB())
    monkeypatch.setattr('app.services.live_paper_test_mode.OrchestratorService.get_state', lambda *_a, **_k: 'paused')
    monkeypatch.setattr(
        svc,
        '_load_candidates',
        lambda _db: [{'strategy_instance_id': 'inst_1', 'market': 'SOL/USD', 'current_position_qty': 0}],
    )

    calls = {'submit': 0, 'events': []}

    class _FakeAdapter:
        def __init__(self, _db):
            self.bridge = type('Bridge', (), {'enabled': True, 'base_url': 'http://x'})()

        def submit_order(self, _intent):
            calls['submit'] += 1
            return {'accepted': True}

    async def _broadcast(evt):
        calls['events'].append(evt)

    monkeypatch.setattr('app.services.live_paper_test_mode.FreqtradeExecutionAdapter', _FakeAdapter)
    monkeypatch.setattr('app.services.live_paper_test_mode.ws_hub.broadcast', _broadcast)

    asyncio.run(svc.run_once())

    assert calls['submit'] == 0
    assert any(e['type'] == 'paper_test.decision' for e in calls['events'])


def test_auto_order_attempt_when_running_and_rate_limits_respected(monkeypatch):
    svc = LivePaperTestModeService()

    monkeypatch.setattr('app.services.live_paper_test_mode.SessionLocal', lambda: _FakeDB())
    monkeypatch.setattr('app.services.live_paper_test_mode.OrchestratorService.get_state', lambda *_a, **_k: 'running')
    monkeypatch.setattr(
        svc,
        '_load_candidates',
        lambda _db: [{'strategy_instance_id': 'inst_1', 'market': 'SOL/USD', 'current_position_qty': 0}],
    )

    monkeypatch.setattr(settings, 'live_paper_test_min_seconds_between_orders', 9999.0)
    monkeypatch.setattr(settings, 'live_paper_test_max_orders_per_minute', 10)
    monkeypatch.setattr(settings, 'live_paper_test_order_qty', 0.1)
    monkeypatch.setattr(settings, 'live_paper_test_force_paper_only', True)

    calls = {'submit': 0, 'events': []}

    class _FakeAdapter:
        def __init__(self, _db):
            self.bridge = type('Bridge', (), {'enabled': True, 'base_url': 'http://x'})()

        def submit_order(self, _intent):
            calls['submit'] += 1
            return {'accepted': True, 'order_id': f'ord_{calls["submit"]}'}

    async def _broadcast(evt):
        calls['events'].append(evt)

    monkeypatch.setattr('app.services.live_paper_test_mode.FreqtradeExecutionAdapter', _FakeAdapter)
    monkeypatch.setattr('app.services.live_paper_test_mode.ws_hub.broadcast', _broadcast)

    asyncio.run(svc.run_once())
    asyncio.run(svc.run_once())

    assert calls['submit'] == 1
    assert any(e['type'] == 'paper_test.order_attempt' for e in calls['events'])
    assert any(e['type'] == 'paper_test.decision' and e.get('reason') == 'min_interval_guard' for e in calls['events'])
