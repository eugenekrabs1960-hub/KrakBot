from __future__ import annotations

import time

from app.adapters.wallet_intel_base import ProviderWalletEvent


class HeliusProviderStub:
    name = "helius"

    async def fetch_wallet_events(self, *, cursor: str | None = None, limit: int = 500):
        # MVP stub: wiring placeholder for production adapter.
        now_ms = int(time.time() * 1000)
        events = [
            ProviderWalletEvent(
                provider=self.name,
                chain="solana",
                provider_event_id=f"helius_stub_{now_ms}",
                wallet_address="wallet_demo_1",
                event_ts=now_ms,
                payload={"kind": "swap", "asset": "SOL", "side_hint": "buy", "qty": 1.25, "price_ref": 86.0},
            )
        ]
        return events[:limit], None


class DuneProviderStub:
    name = "dune"

    async def fetch_wallet_events(self, *, cursor: str | None = None, limit: int = 500):
        return [], None
