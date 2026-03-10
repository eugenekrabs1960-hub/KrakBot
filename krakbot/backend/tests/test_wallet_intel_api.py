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


def test_wallet_intel_pipeline_and_cohort(api_base: str):
    health_before = requests.get(f"{api_base}/wallet-intel/health", timeout=TIMEOUT)
    health_before.raise_for_status()

    run = requests.post(
        f"{api_base}/wallet-intel/admin/run-pipeline",
        json={"provider": "helius"},
        timeout=TIMEOUT,
    )
    run.raise_for_status()
    body = run.json()
    assert body["ok"] is True
    assert body["run_id"].startswith("wrun_")

    latest = requests.get(f"{api_base}/wallet-intel/cohorts/top_sol_active_wallets/latest", timeout=TIMEOUT)
    latest.raise_for_status()
    latest_body = latest.json()
    assert "snapshot" in latest_body
    if latest_body["snapshot"] is not None:
        assert latest_body["snapshot"]["cohort_id"] == "top_sol_active_wallets"
