from __future__ import annotations

import json
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
            return [], cursor

        out: list[ProviderWalletEvent] = []
        cursor_map = self._decode_cursor(cursor)
        next_cursor_map = dict(cursor_map)

        per_addr_limit = max(10, min(100, int(settings.wallet_intel_helius_page_limit)))
        max_pages = max(1, int(settings.wallet_intel_helius_max_pages_per_run))

        for address in self.watchlist:
            before = cursor_map.get(address)
            pages = 0
            while len(out) < limit and pages < max_pages:
                txs = self._fetch_address_transactions(address=address, limit=min(per_addr_limit, limit), before=before)
                if not txs:
                    break

                for tx in txs:
                    evt = self._to_event(address, tx)
                    if evt is not None:
                        out.append(evt)
                        if len(out) >= limit:
                            break

                pages += 1
                last_sig = self._tx_signature(txs[-1])
                if not last_sig or len(txs) < per_addr_limit:
                    before = last_sig
                    break
                before = last_sig

            if before:
                next_cursor_map[address] = before

        return out[:limit], json.dumps(next_cursor_map, sort_keys=True)

    def _decode_cursor(self, cursor: str | None) -> dict[str, str]:
        if not cursor:
            return {}
        try:
            parsed = json.loads(cursor)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items() if v}
        except Exception:
            return {}
        return {}

    def _tx_signature(self, tx: dict[str, Any]) -> str | None:
        signature = str(tx.get("signature") or tx.get("transactionSignature") or "").strip()
        return signature or None

    def _fetch_address_transactions(self, *, address: str, limit: int = 100, before: str | None = None) -> list[dict[str, Any]]:
        url = f"{self.base_url}/v0/addresses/{address}/transactions"
        params: dict[str, Any] = {"api-key": self.api_key, "limit": limit}
        if before:
            params["before"] = before

        retries = max(1, int(settings.wallet_intel_helius_retry_attempts))
        backoff_ms = max(100, int(settings.wallet_intel_helius_retry_backoff_ms))

        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                resp = requests.get(url, params=params, timeout=20)
                # Retry on explicit throttling and 5xx.
                if resp.status_code in {429, 500, 502, 503, 504}:
                    wait_s = (backoff_ms * (2 ** attempt)) / 1000.0
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait_s = max(wait_s, float(retry_after))
                        except ValueError:
                            pass
                    time.sleep(wait_s)
                    continue

                resp.raise_for_status()
                data = resp.json()
                return data if isinstance(data, list) else []
            except requests.RequestException as exc:
                last_err = exc
                if attempt == retries - 1:
                    break
                time.sleep((backoff_ms * (2 ** attempt)) / 1000.0)

        if last_err:
            raise last_err
        return []

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
        return events[:limit], cursor


class DuneProviderStub:
    name = "dune"

    async def fetch_wallet_events(self, *, cursor: str | None = None, limit: int = 500):
        return [], cursor
