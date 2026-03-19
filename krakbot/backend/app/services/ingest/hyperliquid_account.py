from __future__ import annotations

import requests


HL_INFO_URL = "https://api.hyperliquid.xyz/info"


def fetch_account_snapshot(account_address: str | None = None) -> dict:
    """Read-only account state fetch.

    If no account address is provided, returns neutral local snapshot.
    """
    if not account_address:
        return {
            "equity_usd": 10000.0,
            "free_collateral_usd": 9000.0,
            "daily_pnl_usd": 0.0,
            "source": "local_default",
        }
    try:
        r = requests.post(HL_INFO_URL, json={"type": "clearinghouseState", "user": account_address}, timeout=10)
        r.raise_for_status()
        body = r.json()
        margin = body.get("marginSummary", {})
        return {
            "equity_usd": float(margin.get("accountValue") or 0.0),
            "free_collateral_usd": float(margin.get("totalNtlPos") and (float(margin.get("accountValue") or 0.0) - float(margin.get("totalNtlPos") or 0.0)) or margin.get("accountValue") or 0.0),
            "daily_pnl_usd": 0.0,
            "source": "hyperliquid_account",
        }
    except Exception:
        return {
            "equity_usd": 10000.0,
            "free_collateral_usd": 9000.0,
            "daily_pnl_usd": 0.0,
            "source": "fallback",
        }
