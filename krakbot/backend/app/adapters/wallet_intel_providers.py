from __future__ import annotations

import time
from typing import Any

import requests

from app.adapters.wallet_intel_base import ProviderWalletEvent
from app.core.config import settings

WRAPPED_SOL_MINT = "So11111111111111111111111111111111111111112"


class HeliusProvider:
    name = "helius"

    def __init__(self):
        self.base_url = settings.wallet_intel_helius_base_url.rstrip("/")
        self.api_key = settings.wallet_intel_helius_api_key
        self.watchlist = [w.strip() for w in settings.wallet_intel_solana_watchlist.split(",") if w.strip()]

    async def fetch_wallet_events(self, *, cursor: str | None = None, limit: int = 200):
        if not self.api_key or not self.watchlist:
            return [], None

        out: list[ProviderWalletEvent] = []
        for address in self.watchlist:
            txs = self._fetch_address_transactions(address=address, limit=min(100, limit))
            for tx in txs:
                evt = self._to_event(address, tx)
                if evt is not None:
                    out.append(evt)
        return out[:limit], None

    def _fetch_address_transactions(self, *, address: str, limit: int = 100) -> list[dict[str, Any]]:
        url = f"{self.base_url}/v0/addresses/{address}/transactions"
        resp = requests.get(url, params={"api-key": self.api_key, "limit": limit}, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    def _to_event(self, address: str, tx: dict[str, Any]) -> ProviderWalletEvent | None:
        signature = str(tx.get("signature") or tx.get("transactionSignature") or "")
        if not signature:
            return None

        event_ts = int((tx.get("timestamp") or int(time.time())) * 1000)
        sol_delta = self._estimate_sol_delta(address, tx)
        side_hint = "buy" if sol_delta > 0 else "sell" if sol_delta < 0 else "unknown"
        qty = abs(sol_delta)

        token_transfers = tx.get("tokenTransfers") or []
        native_transfers = tx.get("nativeTransfers") or []
        is_swap_like = len(token_transfers) >= 1 or len(native_transfers) >= 1
        kind = "swap" if is_swap_like else "transfer"

        return ProviderWalletEvent(
            provider=self.name,
            chain="solana",
            provider_event_id=signature,
            wallet_address=address,
            event_ts=event_ts,
            payload={
                "kind": kind,
                "asset": "SOL",
                "side_hint": side_hint,
                "qty": qty,
                "price_ref": settings.wallet_intel_default_price_ref_usd,
                "source": "helius_enhanced_tx",
                "raw_type": tx.get("type"),
            },
        )

    def _estimate_sol_delta(self, address: str, tx: dict[str, Any]) -> float:
        lamports_delta = 0

        for nt in tx.get("nativeTransfers") or []:
            amount = int(nt.get("amount") or 0)
            if nt.get("toUserAccount") == address:
                lamports_delta += amount
            if nt.get("fromUserAccount") == address:
                lamports_delta -= amount

        for tt in tx.get("tokenTransfers") or []:
            if tt.get("mint") != WRAPPED_SOL_MINT:
                continue
            amount = float(tt.get("tokenAmount") or 0.0)
            if tt.get("toUserAccount") == address:
                lamports_delta += int(amount * 1_000_000_000)
            if tt.get("fromUserAccount") == address:
                lamports_delta -= int(amount * 1_000_000_000)

        return lamports_delta / 1_000_000_000.0


class HeliusProviderStub:
    name = "helius"

    async def fetch_wallet_events(self, *, cursor: str | None = None, limit: int = 500):
        now_ms = int(time.time() * 1000)
        events = [
            ProviderWalletEvent(
                provider=self.name,
                chain="solana",
                provider_event_id=f"helius_stub_{now_ms}",
                wallet_address="wallet_demo_1",
                event_ts=now_ms,
                payload={"kind": "swap", "asset": "SOL", "side_hint": "buy", "qty": 1.25, "price_ref": settings.wallet_intel_default_price_ref_usd},
            )
        ]
        return events[:limit], None


class DuneProviderStub:
    name = "dune"

    async def fetch_wallet_events(self, *, cursor: str | None = None, limit: int = 500):
        return [], None
