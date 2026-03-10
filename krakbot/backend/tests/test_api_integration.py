import os
import time
import uuid

import pytest
import requests

API_BASE = os.getenv("KRAKBOT_API_BASE", "http://localhost:8010/api")
TIMEOUT = float(os.getenv("KRAKBOT_TEST_TIMEOUT", "10"))


@pytest.fixture(scope="module")
def api_base() -> str:
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:  # pragma: no cover - integration guard
        pytest.skip(f"API stack not reachable at {API_BASE}: {exc}")
    return API_BASE


def test_control_state_transitions(api_base: str):
    # Force a known state before transitions.
    r = requests.post(f"{api_base}/control/bot", json={"command": "stop"}, timeout=TIMEOUT)
    r.raise_for_status()
    assert r.json()["state"] == "stopped"

    transitions = [
        ("start", "running"),
        ("pause", "paused"),
        ("resume", "running"),
        ("reload", "running"),
        ("stop", "stopped"),
    ]

    for cmd, expected in transitions:
        resp = requests.post(f"{api_base}/control/bot", json={"command": cmd}, timeout=TIMEOUT)
        resp.raise_for_status()
        assert resp.json()["state"] == expected

    state = requests.get(f"{api_base}/control/bot", timeout=TIMEOUT)
    state.raise_for_status()
    assert state.json()["state"] == "stopped"


def _create_strategy_instance(api_base: str) -> str:
    payload = {
        "strategy_name": "trend_following",
        "market": "SOL/USD",
        "instrument_type": "spot",
        "starting_equity_usd": 10000,
        "params": {"test_run": True},
    }
    resp = requests.post(f"{api_base}/strategies/instances", json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()["strategy_instance_id"]


def _paper_order(api_base: str, idem_key: str, payload: dict) -> dict:
    resp = requests.post(
        f"{api_base}/trades/paper-order",
        headers={"x-idempotency-key": idem_key},
        json=payload,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _require_solusd_market_trade(api_base: str, attempts: int = 6, interval_sec: float = 0.5) -> None:
    for _ in range(attempts):
        resp = requests.get(f"{api_base}/market/trades?limit=1", timeout=TIMEOUT)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if items and items[0].get("market") == "SOL/USD":
            return
        time.sleep(interval_sec)
    pytest.skip("Skipping: no recent SOL/USD market trade in /api/market/trades?limit=1")


def test_idempotent_paper_orders(api_base: str):
    _require_solusd_market_trade(api_base)
    strategy_instance_id = _create_strategy_instance(api_base)
    payload = {
        "strategy_instance_id": strategy_instance_id,
        "market": "SOL/USD",
        "side": "buy",
        "qty": 0.2,
        "order_type": "limit",
        "limit_price": 150.0,
    }
    idem_key = f"itest-{uuid.uuid4().hex}"

    first = _paper_order(api_base, idem_key, payload)
    second = _paper_order(api_base, idem_key, payload)

    assert first["accepted"] is True
    assert first["order_id"]
    assert first["execution_id"]

    assert second == first


def test_failure_when_no_trade_price_no_side_effects_and_replay_identical(api_base: str):
    strategy_instance_id = _create_strategy_instance(api_base)
    bad_market = f"NOFEED/{uuid.uuid4().hex[:6]}"

    before = requests.get(f"{api_base}/trades?limit=500", timeout=TIMEOUT)
    before.raise_for_status()
    before_count = len([t for t in before.json()["items"] if t["strategy_instance_id"] == strategy_instance_id])

    payload = {
        "strategy_instance_id": strategy_instance_id,
        "market": bad_market,
        "side": "buy",
        "qty": 0.2,
        "order_type": "market",
    }
    idem_key = f"itest-no-price-{uuid.uuid4().hex}"

    first = _paper_order(api_base, idem_key, payload)
    second = _paper_order(api_base, idem_key, payload)

    assert first == {
        "accepted": False,
        "error_code": "no_market_trade_price",
        "message": "No market trade price available for fill",
        "market": bad_market,
    }
    assert second == first

    after = requests.get(f"{api_base}/trades?limit=500", timeout=TIMEOUT)
    after.raise_for_status()
    after_count = len([t for t in after.json()["items"] if t["strategy_instance_id"] == strategy_instance_id])
    assert after_count == before_count


def test_unknown_market_rejected_with_no_market_trade_price(api_base: str):
    strategy_instance_id = _create_strategy_instance(api_base)
    payload = {
        "strategy_instance_id": strategy_instance_id,
        "market": "ABC/USD",
        "side": "buy",
        "qty": 0.1,
        "order_type": "market",
    }

    result = _paper_order(api_base, f"itest-unknown-market-{uuid.uuid4().hex}", payload)
    assert result["accepted"] is False
    assert result["error_code"] == "no_market_trade_price"


def test_strategy_list_detail_and_trade_history_consistency_after_fills(api_base: str):
    _require_solusd_market_trade(api_base)
    strategy_instance_id = _create_strategy_instance(api_base)

    buy = _paper_order(
        api_base,
        f"itest-buy-{uuid.uuid4().hex}",
        {
            "strategy_instance_id": strategy_instance_id,
            "market": "SOL/USD",
            "side": "buy",
            "qty": 1.0,
            "order_type": "limit",
            "limit_price": 100.0,
        },
    )
    sell = _paper_order(
        api_base,
        f"itest-sell-{uuid.uuid4().hex}",
        {
            "strategy_instance_id": strategy_instance_id,
            "market": "SOL/USD",
            "side": "sell",
            "qty": 1.0,
            "order_type": "limit",
            "limit_price": 110.0,
        },
    )

    assert buy["accepted"] is True
    assert sell["accepted"] is True

    strategies = requests.get(f"{api_base}/strategies", timeout=TIMEOUT)
    strategies.raise_for_status()
    rows = strategies.json()
    row = next((r for r in rows if r["strategy_instance_id"] == strategy_instance_id), None)
    assert row is not None
    assert row["trade_count"] >= 2
    assert float(row["current_position_qty"]) == pytest.approx(0.0)

    detail = requests.get(f"{api_base}/strategies/{strategy_instance_id}", timeout=TIMEOUT)
    detail.raise_for_status()
    item = detail.json()["item"]
    assert item is not None
    assert item["strategy_instance_id"] == strategy_instance_id
    assert float(item["current_position_qty"]) == pytest.approx(0.0)
    assert float(item["realized_pnl_usd"]) == pytest.approx(10.0)

    trades = requests.get(f"{api_base}/trades?limit=200", timeout=TIMEOUT)
    trades.raise_for_status()
    items = [t for t in trades.json()["items"] if t["strategy_instance_id"] == strategy_instance_id]
    assert len(items) >= 2

    trade_sides = {t["side"] for t in items}
    assert "buy" in trade_sides
    assert "sell" in trade_sides

    trade_qty_sum = sum(float(t["qty"]) if t["side"] == "buy" else -float(t["qty"]) for t in items)
    assert trade_qty_sum == pytest.approx(0.0)

    order_ids = {buy["order_id"], sell["order_id"]}
    execution_ids = {buy["execution_id"], sell["execution_id"]}
    assert len(order_ids) == 2
    assert len(execution_ids) == 2
