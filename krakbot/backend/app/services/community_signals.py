from __future__ import annotations

import time
import requests

from app.core.config import settings

_CACHE: tuple[float, dict[str, dict]] | None = None


def _clamp(v: float, lo=0.0, hi=1.0) -> float:
    return max(lo, min(hi, v))


def _symbol_from_coin_name(name: str) -> str:
    n = (name or '').lower()
    if 'bitcoin' in n:
        return 'BTC'
    if 'ethereum' in n:
        return 'ETH'
    if 'solana' in n:
        return 'SOL'
    return name[:4].upper() if name else ''


def _fetch_trending_map() -> dict[str, dict]:
    if not settings.community_signal_enabled:
        return {}

    global _CACHE
    now = time.time()
    if _CACHE and (now - _CACHE[0]) < max(60, int(settings.community_signal_ttl_sec)):
        return _CACHE[1]

    out: dict[str, dict] = {}
    try:
        r = requests.get(settings.community_signal_source_url, timeout=6)
        r.raise_for_status()
        j = r.json()
        coins = j.get('coins') or []
        total = max(1, len(coins))

        for idx, row in enumerate(coins):
            item = row.get('item') or {}
            name = item.get('name') or ''
            sym = _symbol_from_coin_name(name)
            rank_factor = 1.0 - (idx / total)
            market_cap_rank = item.get('market_cap_rank') or 500
            mcr = float(market_cap_rank) if str(market_cap_rank).isdigit() else 500.0
            smallcap_boost = _clamp((300.0 - min(300.0, mcr)) / 300.0)

            mention_velocity = _clamp(0.35 + 0.6 * rank_factor)
            trendiness = _clamp(0.4 + 0.5 * rank_factor)
            sentiment = _clamp(0.45 + 0.2 * rank_factor - 0.1 * (1 - smallcap_boost))
            hype = _clamp(0.3 + 0.7 * rank_factor)
            crowd = _clamp(0.25 + 0.55 * rank_factor + 0.2 * smallcap_boost)

            out[sym] = {
                'source': 'coingecko_trending_daily',
                'mention_velocity_score': round(mention_velocity, 4),
                'trendiness_score': round(trendiness, 4),
                'sentiment_score': round(sentiment, 4),
                'hype_score': round(hype, 4),
                'crowding_risk': round(crowd, 4),
                'summary_text': f"{name} trending rank #{idx + 1} with elevated community attention.",
            }
    except Exception:
        out = {}

    _CACHE = (now, out)
    return out


def get_community_summary(coin: str) -> dict | None:
    if not settings.community_signal_enabled:
        return None
    m = _fetch_trending_map()
    sym = (coin or '').upper()
    if sym in m:
        return m[sym]
    return {
        'source': 'coingecko_trending_daily',
        'mention_velocity_score': 0.2,
        'trendiness_score': 0.2,
        'sentiment_score': 0.5,
        'hype_score': 0.2,
        'crowding_risk': 0.2,
        'summary_text': f"{sym} not currently in top trending list.",
    }
