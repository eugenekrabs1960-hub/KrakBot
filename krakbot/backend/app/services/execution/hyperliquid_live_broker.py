from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import requests

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.db_models import LiveRelayRequestDB
from app.services.execution.broker_base import BrokerBase


HL_INFO_URL = "https://api.hyperliquid.xyz/info"


class HyperliquidLiveBroker(BrokerBase):
    """Live broker first implementation with idempotent relay writes."""

    def _idem_key(self, payload: dict) -> str:
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()[:40]

    def _relay(self, payload: dict) -> dict:
        idem = self._idem_key(payload)

        with SessionLocal() as db:
            existing = db.get(LiveRelayRequestDB, idem)
            if existing:
                return existing.response

        if not settings.hyperliquid_order_relay_url:
            response = {"accepted": False, "reason": "relay_not_configured", "idempotency_key": idem}
        else:
            headers = {"X-Idempotency-Key": idem}
            if settings.hyperliquid_order_relay_token:
                headers["Authorization"] = f"Bearer {settings.hyperliquid_order_relay_token}"
            r = requests.post(settings.hyperliquid_order_relay_url, json=payload, headers=headers, timeout=15)
            if r.status_code >= 400:
                response = {"accepted": False, "reason": f"relay_error_{r.status_code}", "body": r.text[:400], "idempotency_key": idem}
            else:
                body = r.json()
                if "accepted" not in body:
                    body["accepted"] = bool(body.get("status") == "ok")
                body["idempotency_key"] = idem
                response = body

        with SessionLocal() as db:
            db.add(LiveRelayRequestDB(
                idempotency_key=idem,
                action=str(payload.get("action", "unknown")),
                status="ok" if response.get("accepted") else "rejected",
                payload=payload,
                response=response,
                created_at=datetime.now(timezone.utc),
            ))
            db.commit()

        return response

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
