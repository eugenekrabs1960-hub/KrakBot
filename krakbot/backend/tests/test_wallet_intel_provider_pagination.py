import json

from app.adapters.wallet_intel_providers import HeliusProvider
from app.core.config import settings


def test_helius_provider_cursor_pagination(monkeypatch):
    p = HeliusProvider()
    monkeypatch.setattr(settings, 'wallet_intel_helius_page_limit', 2, raising=False)
    monkeypatch.setattr(settings, 'wallet_intel_helius_max_pages_per_run', 1, raising=False)
    p.api_key = 'x'
    p.watchlist = ['wallet_a']

    calls = []

    def fake_fetch(self, address, limit=100, before=None):
        calls.append({'address': address, 'before': before, 'limit': limit})
        if before is None:
            return [
                {'signature': 'sig_3', 'timestamp': 1, 'nativeTransfers': [], 'tokenTransfers': []},
                {'signature': 'sig_2', 'timestamp': 1, 'nativeTransfers': [], 'tokenTransfers': []},
            ]
        if before == 'sig_2':
            return [
                {'signature': 'sig_1', 'timestamp': 1, 'nativeTransfers': [], 'tokenTransfers': []},
            ]
        return []

    monkeypatch.setattr(HeliusProvider, '_fetch_address_transactions', fake_fetch)

    events, cursor = __import__('asyncio').run(p.fetch_wallet_events(limit=5))
    assert len(events) == 2
    cursor_map = json.loads(cursor)
    assert cursor_map['wallet_a'] == 'sig_2'
    assert calls[0]['before'] is None

    calls.clear()
    events2, cursor2 = __import__('asyncio').run(p.fetch_wallet_events(cursor=cursor, limit=5))
    assert len(events2) == 1
    assert calls[0]['before'] == 'sig_2'
    cursor_map2 = json.loads(cursor2)
    assert cursor_map2['wallet_a'] == 'sig_1'
