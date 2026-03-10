import json
from pathlib import Path

import pytest
from sqlalchemy import text
from app.core.config import settings
from app.services.eif_capture import EIFCaptureService
from app.services.live_paper_test_mode import LivePaperTestModeService


class _FakeResult:
    def __init__(self, row=None, scalar=None):
        self._row = row or {"sample_size": 0}
        self._scalar = scalar

    def mappings(self):
        return self

    def first(self):
        return self._row

    def all(self):
        return [self._row]

    def scalar_one(self):
        return self._scalar


class _FakeDB:
    def __init__(self):
        self.calls = []
        self.commits = 0

    def execute(self, stmt, params=None):
        sql = str(stmt)
        params = params or {}
        self.calls.append((sql, params))

        if "INSERT INTO eif_regime_snapshots" in sql:
            return _FakeResult(scalar=101)
        return _FakeResult()

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


def test_eif_capture_normalizes_invalid_taxonomy(monkeypatch):
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
        event_type="not_a_real_type",
        decision="random_decision",
        reason_code="not_a_real_reason",
        allowed=False,
        tags=["mode:paper", "event:wat", "freeform:value"],
    )

    _, filter_params = next((c for c in db.calls if "INSERT INTO eif_filter_decisions" in c[0]), (None, None))
    assert filter_params is not None
    assert filter_params["event_type"] == "decision"
    assert filter_params["decision"] == "unknown"
    assert filter_params["reason_code"] == "unknown"
    assert json.loads(filter_params["tags"]) == ["mode:paper", "risk:unknown"]


def test_eif_capture_writes_regime_snapshot_fk_id(monkeypatch):
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

    _, filter_params = next((c for c in db.calls if "INSERT INTO eif_filter_decisions" in c[0]), (None, None))
    assert filter_params is not None
    assert filter_params["regime_snapshot_id"] == 101


def test_eif_recent_events_limit_validation():
    from app.api.routes.eif import eif_recent_events

    fake_db = _FakeDB()

    resp = eif_recent_events(limit=0, db=fake_db)
    assert resp["limit"] == 1
    assert fake_db.calls[-1][1]["limit"] == 1

    resp = eif_recent_events(limit=999, db=fake_db)
    assert resp["limit"] == 500
    assert fake_db.calls[-1][1]["limit"] == 500


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


def test_live_paper_shadow_mode_does_not_block(monkeypatch):
    svc = LivePaperTestModeService()

    monkeypatch.setattr('app.services.live_paper_test_mode.SessionLocal', lambda: _FakeDB())
    monkeypatch.setattr('app.services.live_paper_test_mode.OrchestratorService.get_state', lambda *_a, **_k: 'running')
    monkeypatch.setattr(
        svc,
        '_load_candidates',
        lambda _db: [{'strategy_instance_id': 'inst_1', 'market': 'SOL/USD', 'strategy_name': 'trend_following', 'current_position_qty': 0}],
    )
    monkeypatch.setattr(settings, 'live_paper_test_min_seconds_between_orders', 0.0)
    monkeypatch.setattr(settings, 'live_paper_test_max_orders_per_minute', 99)
    monkeypatch.setattr(settings, 'live_paper_test_order_qty', 0.1)

    class _Eval:
        allowed = True
        reason_code = 'shadow_data_stale'
        traces = []
        blocked_stage = 'data_integrity'
        shadow_mode = True
        enforce_mode = False

    monkeypatch.setattr('app.services.live_paper_test_mode.eif_filter_engine.evaluate', lambda *_a, **_k: _Eval())

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
    assert calls['submit'] == 1


def test_live_paper_enforce_mode_blocks(monkeypatch):
    svc = LivePaperTestModeService()

    monkeypatch.setattr('app.services.live_paper_test_mode.SessionLocal', lambda: _FakeDB())
    monkeypatch.setattr('app.services.live_paper_test_mode.OrchestratorService.get_state', lambda *_a, **_k: 'running')
    monkeypatch.setattr(
        svc,
        '_load_candidates',
        lambda _db: [{'strategy_instance_id': 'inst_1', 'market': 'SOL/USD', 'strategy_name': 'trend_following', 'current_position_qty': 0}],
    )
    monkeypatch.setattr(settings, 'live_paper_test_min_seconds_between_orders', 0.0)
    monkeypatch.setattr(settings, 'live_paper_test_max_orders_per_minute', 99)
    monkeypatch.setattr(settings, 'live_paper_test_order_qty', 0.1)

    class _Eval:
        allowed = False
        reason_code = 'spread_too_wide'
        traces = []
        blocked_stage = 'hard_risk'
        shadow_mode = False
        enforce_mode = True

    monkeypatch.setattr('app.services.live_paper_test_mode.eif_filter_engine.evaluate', lambda *_a, **_k: _Eval())

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
    assert calls['submit'] == 0


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


def test_eif_analytics_api_guard(monkeypatch):
    from app.api.routes.eif import eif_summary

    fake_db = _FakeDB()
    monkeypatch.setattr(settings, 'eif_analytics_api_enabled', False)
    out = eif_summary(db=fake_db)
    assert out['analytics_api_enabled'] is False


def test_eif_filter_decisions_endpoint_bounded(monkeypatch):
    from app.api.routes.eif import eif_filter_decisions

    fake_db = _FakeDB()
    monkeypatch.setattr(settings, 'eif_analytics_api_enabled', True)
    out = eif_filter_decisions(limit=999, offset=-5, db=fake_db)
    assert out['limit'] == 200
    assert out['offset'] == 0


def test_eif_trade_trace_normalizes_nullable_payloads(monkeypatch):
    from app.api.routes.eif import eif_trade_trace

    class _TraceDB(_FakeDB):
        def execute(self, stmt, params=None):
            sql = str(stmt)
            self.calls.append((sql, params or {}))
            if "FROM eif_trade_context_events" in sql:
                return _FakeResult(row={"id": 1, "strategy_instance_id": "inst_1", "market": "SOL/USD", "event_type": "entry", "tags": None, "context": None, "ts": "2026-01-01T00:00:00Z"})
            return _FakeResult()

    fake_db = _TraceDB()
    monkeypatch.setattr(settings, 'eif_analytics_api_enabled', True)
    out = eif_trade_trace(limit=1, db=fake_db)
    assert out['items'][0]['tags'] == []
    assert out['items'][0]['context'] == {}


def test_eif_filter_decisions_includes_regime_snapshot_field(monkeypatch):
    from app.api.routes.eif import eif_filter_decisions

    class _DecisionDB(_FakeDB):
        def execute(self, stmt, params=None):
            sql = str(stmt)
            self.calls.append((sql, params or {}))
            if "FROM eif_filter_decisions" in sql and "GROUP BY reason_code" not in sql:
                return _FakeResult(row={"id": 9, "reason_code": "ok", "regime_snapshot_id": 42})
            if "GROUP BY reason_code" in sql:
                return _FakeResult(row={"reason_code": "ok", "count": 1})
            return _FakeResult()

    fake_db = _DecisionDB()
    monkeypatch.setattr(settings, 'eif_analytics_api_enabled', True)
    out = eif_filter_decisions(limit=1, db=fake_db)
    assert out['items'][0]['regime_snapshot_id'] == 42


def test_migration_0008_adds_regime_snapshot_fk_if_database_available():
    from app.db.session import engine

    migration_path = Path(__file__).resolve().parents[1] / "app" / "db" / "migrations" / "0008_eif_phase1_1_integrity.sql"
    sql = migration_path.read_text()

    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
            col = conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'eif_filter_decisions'
                      AND column_name = 'regime_snapshot_id'
                    """
                )
            ).scalar()
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(f"DB not available for migration apply test: {exc}")

    assert col == 'regime_snapshot_id'


def test_migration_0009_adds_filter_trace_columns_if_database_available():
    from app.db.session import engine

    migration_path = Path(__file__).resolve().parents[1] / "app" / "db" / "migrations" / "0009_eif_phase2_filter_engine.sql"
    sql = migration_path.read_text()

    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
            col = conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'eif_filter_decisions'
                      AND column_name IN ('trace', 'precedence_stage', 'shadow_mode', 'enforce_mode', 'filter_engine_version')
                    """
                )
            ).fetchall()
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(f"DB not available for migration apply test: {exc}")

    assert len(col) == 5
