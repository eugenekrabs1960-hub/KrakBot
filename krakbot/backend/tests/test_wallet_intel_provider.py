import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.adapters.wallet_intel_providers import HeliusProvider


def test_helius_estimate_sol_delta_native_transfer():
    p = HeliusProvider()
    address = "wallet_abc"
    tx = {
        "nativeTransfers": [
            {"toUserAccount": address, "fromUserAccount": "x", "amount": 2_000_000_000},
            {"toUserAccount": "y", "fromUserAccount": address, "amount": 500_000_000},
        ],
        "tokenTransfers": [],
    }
    delta = p._estimate_sol_delta(address, tx)
    assert abs(delta - 1.5) < 1e-9
