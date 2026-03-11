from __future__ import annotations

from app.execution.protocols import VenueAdapter


class VenueGateway:
    def __init__(self):
        self._adapters: dict[str, VenueAdapter] = {}

    def register(self, venue: str, adapter: VenueAdapter) -> None:
        self._adapters[venue] = adapter

    def get(self, venue: str) -> VenueAdapter:
        if venue not in self._adapters:
            raise KeyError(f'venue adapter not registered: {venue}')
        return self._adapters[venue]

    def list_venues(self) -> list[str]:
        return sorted(self._adapters.keys())
