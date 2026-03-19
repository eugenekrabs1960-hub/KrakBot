from __future__ import annotations

import requests

from app.core.config import settings
from app.services.execution.broker_base import BrokerBase


HL_INFO_URL = "https://api.hyperliquid.xyz/info"


class HyperliquidLiveBroker(BrokerBase):
    """Live broker first implementation.

    Uses read-only Hyperliquid info endpoints directly.
    For write operations, routes to a configurable local relay that performs
    wallet signing. This keeps signing keys out of the app process.
    """

    def _relay(self, payload: dict) -> dict:
        if not settings.hyperliquid_order_relay_url:
            return {"accepted": False, "reason": "relay_not_configured"}
        headers = {}
        if settings.hyperliquid_order_relay_token:
            headers["Authorization"] = f"Bearer {settings.hyperliquid_order_relay_token}"
        r = requests.post(settings.hyperliquid_order_relay_url, json=payload, headers=headers, timeout=15)
        if r.status_code >= 400:
            return {"accepted": False, "reason": f"relay_error_{r.status_code}", "body": r.text[:400]}
        body = r.json()
        if "accepted" not in body:
            body["accepted"] = bool(body.get("status") == "ok")
        return body

    def place_order(self, symbol: str, side: str, notional_usd: float, reduce_only: bool = False) -> dict:
        return self._relay({
            "action": "place_order",
            "symbol": symbol,
            "side": side,
            "notional_usd": notional_usd,
            "reduce_only": reduce_only,
            "account": settings.hyperliquid_account_address,
        })

    def cancel_order(self, order_id: str) -> dict:
        return self._relay({"action": "cancel_order", "order_id": order_id, "account": settings.hyperliquid_account_address})

    def get_open_orders(self) -> list[dict]:
        if not settings.hyperliquid_account_address:
            return []
        try:
            r = requests.post(HL_INFO_URL, json={"type": "openOrders", "user": settings.hyperliquid_account_address}, timeout=10)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def get_positions(self) -> list[dict]:
        if not settings.hyperliquid_account_address:
            return []
        try:
            r = requests.post(HL_INFO_URL, json={"type": "clearinghouseState", "user": settings.hyperliquid_account_address}, timeout=10)
            r.raise_for_status()
            body = r.json()
            out = []
            for p in body.get("assetPositions", []):
                pos = p.get("position", {})
                out.append({
                    "symbol": pos.get("coin", "") + "-PERP",
                    "qty": float(pos.get("szi") or 0.0),
                    "entry_px": float(pos.get("entryPx") or 0.0),
                    "unrealized_pnl": float(pos.get("unrealizedPnl") or 0.0),
                })
            return out
        except Exception:
            return []

    def get_fills(self) -> list[dict]:
        if not settings.hyperliquid_account_address:
            return []
        try:
            r = requests.post(HL_INFO_URL, json={"type": "userFills", "user": settings.hyperliquid_account_address}, timeout=10)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def flatten_position(self, symbol: str) -> dict:
        return self._relay({"action": "flatten_position", "symbol": symbol, "account": settings.hyperliquid_account_address})

    def flatten_all_positions(self) -> dict:
        return self._relay({"action": "flatten_all_positions", "account": settings.hyperliquid_account_address})


hyperliquid_live_broker = HyperliquidLiveBroker()
