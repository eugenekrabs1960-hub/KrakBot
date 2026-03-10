from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ProviderWalletEvent:
    provider: str
    chain: str
    provider_event_id: str
    wallet_address: str
    event_ts: int
    payload: dict


class WalletIntelProvider(Protocol):
    name: str

    async def fetch_wallet_events(self, *, cursor: str | None = None, limit: int = 500) -> tuple[list[ProviderWalletEvent], str | None]:
        ...
