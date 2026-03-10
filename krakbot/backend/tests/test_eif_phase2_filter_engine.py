from app.core.config import settings
from app.services.eif_filter_engine import EIFFilterEngine


class _FakeDB:
    pass


def _candidate():
    return {"strategy_instance_id": "inst_1", "market": "SOL/USD", "strategy_name": "trend_following"}


def test_filter_precedence_data_integrity_beats_risk(monkeypatch):
    engine = EIFFilterEngine()
    monkeypatch.setattr(settings, "eif_filter_shadow_mode", False)
    monkeypatch.setattr(settings, "eif_filter_enforce_mode", True)
    monkeypatch.setattr(settings, "eif_filter_fail_closed", False)

    monkeypatch.setattr(
        engine,
        "_load_metrics",
        lambda *_a, **_k: {
            "latest_trade_ts": 0,
            "trade_count_200": 100,
            "qty_5m": 100,
            "bids": [[100, 0.1]],
            "asks": [[103, 0.1]],
            "min_close_30": 99,
            "max_close_30": 101,
            "avg_close_30": 100,
            "consecutive_losses": 0,
            "max_drawdown": 0,
        },
    )
    monkeypatch.setattr(engine._regime_builder, "build", lambda *_a, **_k: {"trend": "up", "volatility": "normal"})

    out = engine.evaluate(_FakeDB(), _candidate(), "enter")
    assert out.allowed is False
    assert out.reason_code == "data_stale"
    assert out.blocked_stage == "data_integrity"


def test_shadow_mode_never_blocks(monkeypatch):
    engine = EIFFilterEngine()
    monkeypatch.setattr(settings, "eif_filter_shadow_mode", True)
    monkeypatch.setattr(settings, "eif_filter_enforce_mode", True)

    monkeypatch.setattr(engine, "_load_metrics", lambda *_a, **_k: {"latest_trade_ts": 0})
    monkeypatch.setattr(engine._regime_builder, "build", lambda *_a, **_k: {"trend": "flat", "volatility": "high"})

    out = engine.evaluate(_FakeDB(), _candidate(), "enter")
    assert out.allowed is True
    assert out.reason_code.startswith("shadow_")


def test_enforce_mode_blocks(monkeypatch):
    engine = EIFFilterEngine()
    monkeypatch.setattr(settings, "eif_filter_shadow_mode", False)
    monkeypatch.setattr(settings, "eif_filter_enforce_mode", True)

    monkeypatch.setattr(
        engine,
        "_load_metrics",
        lambda *_a, **_k: {
            "latest_trade_ts": 9999999999999,
            "trade_count_200": 100,
            "qty_5m": 100,
            "bids": [[100, 0.1]],
            "asks": [[100.01, 0.1]],
            "min_close_30": 99,
            "max_close_30": 101,
            "avg_close_30": 100,
            "consecutive_losses": 5,
            "max_drawdown": 20,
        },
    )
    monkeypatch.setattr(engine._regime_builder, "build", lambda *_a, **_k: {"trend": "up", "volatility": "normal"})

    out = engine.evaluate(_FakeDB(), _candidate(), "enter")
    assert out.allowed is False
    assert out.reason_code == "cooldown_active"


def test_each_core_rule_emits_trace(monkeypatch):
    engine = EIFFilterEngine()
    monkeypatch.setattr(settings, "eif_filter_shadow_mode", True)
    monkeypatch.setattr(settings, "eif_filter_enforce_mode", False)
    monkeypatch.setattr(
        engine,
        "_load_metrics",
        lambda *_a, **_k: {
            "latest_trade_ts": 9999999999999,
            "trade_count_200": 100,
            "qty_5m": 100,
            "bids": [[100, 10], [99.5, 10]],
            "asks": [[100.05, 10], [100.1, 10]],
            "min_close_30": 99,
            "max_close_30": 100.5,
            "avg_close_30": 100,
            "consecutive_losses": 0,
            "max_drawdown": 0,
        },
    )
    monkeypatch.setattr(engine._regime_builder, "build", lambda *_a, **_k: {"trend": "up", "volatility": "normal"})
    out = engine.evaluate(_FakeDB(), _candidate(), "enter")
    rule_ids = {t["rule_id"] for t in out.traces}
    assert rule_ids == {
        "data_staleness",
        "min_activity",
        "spread_cap",
        "volatility_band",
        "liquidity_depth",
        "orderbook_imbalance",
        "regime_strategy_compat",
        "cooldown_loss_drawdown",
    }
