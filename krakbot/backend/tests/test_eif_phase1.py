from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.services.eif_capture import EIFCaptureService
from app.services.live_paper_test_mode import LivePaperTestModeService


class _FakeDB:
    def __init__(self):
        self.calls = []
        self.commits = 0

    def execute(self, stmt, params=None):
        self.calls.append((str(stmt), params or {}))

        class _R:
            def mappings(self):
                return self

            def first(self):
                return {"sample_size": 0}

        return _R()

    def commit(self):
        self.commits += 1

    def close(self):
        pass


def test_eif_flags_default_off():
    assert settings.eif_capture_enabled is False
    assert settings.eif_scorecard_compute_enabled is False


def test_eif_capture_writes_when_enabled(monkeypatch):
    db = _FakeDB()
    svc = EIFCaptureService()

    monkeypatch.setattr(settings, "eif_capture_enabled", True)
    monkeypatch.setattr(
        svc._regime_builder,
        "build",
        lambda *_a, **_k: {
            "strategy_instance_id": "inst_1",
            "market": "SOL/USD",
            "regime_version": "v1",
            "trend": "unknown",
            "volatility": "unknown",
            "liquidity": "unknown",
            "session_structure": "unknown",
            "sample_size": 0,
            "features": {},
            "captured_ts": 1,
        },
    )

    svc.capture_filter_decision(
        db,
        strategy_instance_id="inst_1",
        market="SOL/USD",
        event_type="decision",
        decision="enter",
        reason_code="ok",
        allowed=True,
    )
    svc.capture_trade_context_event(
        db,
        strategy_instance_id="inst_1",
        market="SOL/USD",
        event_type="entry",
        side="buy",
        qty=0.1,
        price=100.0,
        pnl_usd=None,
    )

    sql = "\n".join(s for s, _ in db.calls)
    assert "INSERT INTO eif_regime_snapshots" in sql
    assert "INSERT INTO eif_filter_decisions" in sql
    assert "INSERT INTO eif_trade_context_events" in sql
    assert db.commits == 2


def test_live_paper_flow_unchanged_when_eif_disabled(monkeypatch):
    svc = LivePaperTestModeService()

    monkeypatch.setattr('app.services.live_paper_test_mode.SessionLocal', lambda: _FakeDB())
    monkeypatch.setattr('app.services.live_paper_test_mode.OrchestratorService.get_state', lambda *_a, **_k: 'running')
    monkeypatch.setattr(
        svc,
        '_load_candidates',
        lambda _db: [{'strategy_instance_id': 'inst_1', 'market': 'SOL/USD', 'current_position_qty': 0}],
    )

    monkeypatch.setattr(settings, 'eif_capture_enabled', False)
    monkeypatch.setattr(settings, 'eif_scorecard_compute_enabled', False)
    monkeypatch.setattr(settings, 'live_paper_test_min_seconds_between_orders', 9999.0)
    monkeypatch.setattr(settings, 'live_paper_test_max_orders_per_minute', 10)
    monkeypatch.setattr(settings, 'live_paper_test_order_qty', 0.1)

    calls = {'submit': 0}

    class _FakeAdapter:
        def __init__(self, _db):
            self.bridge = type('Bridge', (), {'enabled': True, 'base_url': 'http://x'})()

        def submit_order(self, _intent):
            calls['submit'] += 1
            return {'accepted': True, 'order_id': 'ord_1'}

    async def _broadcast(_evt):
        return None

    monkeypatch.setattr('app.services.live_paper_test_mode.FreqtradeExecutionAdapter', _FakeAdapter)
    monkeypatch.setattr('app.services.live_paper_test_mode.ws_hub.broadcast', _broadcast)

    import asyncio

    asyncio.run(svc.run_once())
    asyncio.run(svc.run_once())

    assert calls['submit'] == 1


def test_migration_0007_applies_if_database_available():
    from app.db.session import engine

    migration_path = Path(__file__).resolve().parents[1] / "app" / "db" / "migrations" / "0007_eif_phase1_foundation.sql"
    sql = migration_path.read_text()

    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
            reg = conn.execute(text("SELECT to_regclass('public.eif_regime_snapshots') AS t")).scalar()
            ctx = conn.execute(text("SELECT to_regclass('public.eif_trade_context_events') AS t")).scalar()
            dec = conn.execute(text("SELECT to_regclass('public.eif_filter_decisions') AS t")).scalar()
            sc = conn.execute(text("SELECT to_regclass('public.eif_scorecard_snapshots') AS t")).scalar()
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(f"DB not available for migration apply test: {exc}")

    assert reg == 'eif_regime_snapshots'
    assert ctx == 'eif_trade_context_events'
    assert dec == 'eif_filter_decisions'
    assert sc == 'eif_scorecard_snapshots'
