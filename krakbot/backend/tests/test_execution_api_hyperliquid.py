import os

import pytest
import requests

API_BASE = os.getenv("KRAKBOT_API_BASE", "http://localhost:8010/api")
TIMEOUT = float(os.getenv("KRAKBOT_TEST_TIMEOUT", "10"))


@pytest.fixture(scope="module")
def api_base() -> str:
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"API stack not reachable at {API_BASE}: {exc}")
    return API_BASE


def test_hyperliquid_execution_health_endpoint(api_base: str):
    resp = requests.get(f"{api_base}/execution/hyperliquid/health", timeout=TIMEOUT)
    resp.raise_for_status()
    body = resp.json()
    assert body['ok'] is True
    assert body['item']['adapter'] == 'hyperliquid'


def test_hyperliquid_execution_account_positions_shape(api_base: str):
    acc = requests.get(f"{api_base}/execution/hyperliquid/account", timeout=TIMEOUT)
    pos = requests.get(f"{api_base}/execution/hyperliquid/positions", timeout=TIMEOUT)
    acc.raise_for_status()
    pos.raise_for_status()
    assert acc.json()['ok'] is True
    assert pos.json()['ok'] is True
    assert isinstance(pos.json()['items'], list)


def test_hyperliquid_reconciliation_endpoints(api_base: str):
    run = requests.post(f"{api_base}/execution/hyperliquid/reconcile", timeout=TIMEOUT)
    run.raise_for_status()
    body = run.json()
    assert body['ok'] is True
    assert body['status'] in {'ok', 'drift_detected'}

    hist = requests.get(f"{api_base}/execution/hyperliquid/reconcile/history?limit=5", timeout=TIMEOUT)
    hist.raise_for_status()
    h = hist.json()
    assert h['ok'] is True
    assert isinstance(h['items'], list)

    acc = requests.get(f"{api_base}/execution/hyperliquid/snapshots/account?limit=5", timeout=TIMEOUT)
    pos = requests.get(f"{api_base}/execution/hyperliquid/snapshots/positions?limit=5", timeout=TIMEOUT)
    risk = requests.get(f"{api_base}/execution/hyperliquid/risk-snapshot", timeout=TIMEOUT)
    acc.raise_for_status()
    pos.raise_for_status()
    risk.raise_for_status()
    assert acc.json()['ok'] is True
    assert pos.json()['ok'] is True
    assert risk.json()['ok'] is True
    assert isinstance(acc.json()['items'], list)
    assert isinstance(pos.json()['items'], list)
    assert 'margin_utilization_pct' in risk.json()


def test_hyperliquid_collector_and_export_endpoints(api_base: str):
    run = requests.post(f"{api_base}/execution/hyperliquid/collector/run-once", timeout=TIMEOUT)
    run.raise_for_status()
    body = run.json()
    assert 'ok' in body

    status = requests.get(f"{api_base}/execution/hyperliquid/collector/status", timeout=TIMEOUT)
    status.raise_for_status()
    assert status.json()['ok'] is True

    export = requests.get(f"{api_base}/execution/hyperliquid/training-features/export?limit=10", timeout=TIMEOUT)
    export.raise_for_status()
    assert 'id,ts,environment,symbol,mid_price,ret_1,ret_5,ret_15,source' in export.text.splitlines()[0]

    job = requests.post(f"{api_base}/execution/hyperliquid/training-features/export-job?limit=20", timeout=TIMEOUT)
    job.raise_for_status()
    jb = job.json()
    assert 'ok' in jb
