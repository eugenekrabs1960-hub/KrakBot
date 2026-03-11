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

    h = requests.get(f"{api_base}/model-lab/job-history?limit=10", timeout=TIMEOUT)
    h.raise_for_status()
    assert h.json()['ok'] is True

    p_bad = requests.post(f"{api_base}/model-lab/promote-to-paper?symbol=BTC&model_path=/tmp/fake.json&confirm_phrase=NOPE", timeout=TIMEOUT)
    p_bad.raise_for_status()
    assert p_bad.json()['ok'] is False

    p_ok = requests.post(f"{api_base}/model-lab/promote-to-paper?symbol=BTC&model_path=/tmp/fake.json&confirm_phrase=PROMOTE", timeout=TIMEOUT)
    p_ok.raise_for_status()
    assert p_ok.json()['ok'] is True

    ap = requests.get(f"{api_base}/model-lab/active-paper-model", timeout=TIMEOUT)
    ap.raise_for_status()
    assert ap.json()['ok'] is True

    ex = requests.get(f"{api_base}/model-lab/active-execution-model", timeout=TIMEOUT)
    ex.raise_for_status()
    assert ex.json()['ok'] is True

    ex_bad = requests.post(f"{api_base}/model-lab/set-active-execution-model?agent_id=agent_a&confirm_phrase=NOPE", timeout=TIMEOUT)
    ex_bad.raise_for_status()
    assert ex_bad.json()['ok'] is False

    ex_ok = requests.post(f"{api_base}/model-lab/set-active-execution-model?agent_id=agent_a&confirm_phrase=SWITCH", timeout=TIMEOUT)
    ex_ok.raise_for_status()
    assert ex_ok.json()['ok'] is True

    ex_dup = requests.post(f"{api_base}/model-lab/set-active-execution-model?agent_id=agent_a&confirm_phrase=SWITCH", timeout=TIMEOUT)
    ex_dup.raise_for_status()
    assert ex_dup.json()['ok'] is True
    assert ex_dup.json().get('unchanged') is True

    ex_empty = requests.post(f"{api_base}/model-lab/set-active-execution-model?agent_id=%20%20%20&confirm_phrase=SWITCH", timeout=TIMEOUT)
    ex_empty.raise_for_status()
    assert ex_empty.json()['ok'] is False
    assert ex_empty.json().get('error') == 'invalid_agent_id'
