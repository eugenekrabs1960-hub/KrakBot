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
    except Exception as exc:
        pytest.skip(f"API stack not reachable at {API_BASE}: {exc}")
    return API_BASE


def test_model_lab_endpoints_shape(api_base: str):
    b = requests.get(f"{api_base}/model-lab/strategy-benchmarks?symbol=BTC&limit=5000", timeout=TIMEOUT)
    b.raise_for_status()
    assert b.json().get('ok') is True

    t = requests.post(f"{api_base}/model-lab/train-baseline?symbol=BTC&limit=5000", timeout=TIMEOUT)
    t.raise_for_status()
    tj = t.json()
    assert 'ok' in tj

    l = requests.get(f"{api_base}/model-lab/latest-model?symbol=BTC", timeout=TIMEOUT)
    l.raise_for_status()
    assert 'ok' in l.json()
