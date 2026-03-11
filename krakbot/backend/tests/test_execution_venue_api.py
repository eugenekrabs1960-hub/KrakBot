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


def test_control_execution_venue_get_set(api_base: str):
    r1 = requests.get(f"{api_base}/control/execution/venue", timeout=TIMEOUT)
    r1.raise_for_status()
    assert r1.json()["default_venue"] in {"paper", "hyperliquid"}

    r2 = requests.post(f"{api_base}/control/execution/venue", json={"default_venue": "paper"}, timeout=TIMEOUT)
    r2.raise_for_status()
    assert r2.json()["ok"] is True
    assert r2.json()["default_venue"] == "paper"
