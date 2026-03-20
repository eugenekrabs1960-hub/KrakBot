from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

from app.core.config import settings

_CACHE: dict[str, tuple[float, dict | None]] = {}

POS_WORDS = {'surge', 'gain', 'rally', 'beat', 'approval', 'growth', 'adoption', 'bull'}
NEG_WORDS = {'hack', 'lawsuit', 'ban', 'drop', 'selloff', 'crash', 'delay', 'bear'}


def _safe_dt(s: str | None):
    if not s:
        return None
    for fmt in ['%a, %d %b %Y %H:%M:%S %z', '%Y-%m-%dT%H:%M:%S%z']:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def _headline_sentiment(text: str) -> float:
    t = (text or '').lower()
    score = 0
    for w in POS_WORDS:
        if w in t:
            score += 1
    for w in NEG_WORDS:
        if w in t:
            score -= 1
    return max(-1.0, min(1.0, score / 3.0))


def get_news_summary(coin: str, market_snapshot: dict) -> dict | None:
    if not settings.news_signal_enabled:
        return None

    now = time.time()
    k = coin.upper()
    hit = _CACHE.get(k)
    if hit and (now - hit[0]) < max(30, int(settings.news_signal_ttl_sec)):
        return hit[1]

    out = None
    try:
        r = requests.get(settings.news_signal_source_url, timeout=6)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        items = root.findall('.//item')[:40]

        relevant = []
        for it in items:
            title = (it.findtext('title') or '').strip()
            desc = (it.findtext('description') or '').strip()
            pub = (it.findtext('pubDate') or '').strip()
            text = f"{title} {desc}".lower()
            if k.lower() in text or (k == 'BTC' and 'bitcoin' in text) or (k == 'ETH' and 'ethereum' in text) or (k == 'SOL' and 'solana' in text):
                relevant.append({'title': title, 'pub': pub, 'desc': desc})

        if relevant:
            latest = relevant[0]
            latest_dt = _safe_dt(latest.get('pub'))
            age_h = ((datetime.now(timezone.utc) - latest_dt.astimezone(timezone.utc)).total_seconds() / 3600.0) if latest_dt else 24.0
            freshness = max(0.0, min(1.0, 1.0 - age_h / 24.0))
            novelty = max(0.0, min(1.0, len({x['title'] for x in relevant[:5]}) / 5.0))
            sent = _headline_sentiment(' '.join([x['title'] for x in relevant[:3]]))

            spread = float(market_snapshot.get('spread_bps') or 0.0)
            funding = abs(float(market_snapshot.get('funding_rate') or 0.0)) * 10000.0
            priced_in_risk = max(0.0, min(1.0, (spread / 25.0) * 0.6 + (funding / 20.0) * 0.4))

            out = {
                'source': 'coindesk_rss',
                'sentiment_score': sent,
                'novelty_score': novelty,
                'freshness_score': freshness,
                'priced_in_risk_score': priced_in_risk,
                'summary_text': latest['title'][:220],
                'headline_count': len(relevant),
                'latest_published_at': latest.get('pub'),
            }
    except Exception:
        out = {
            'source': 'coindesk_rss',
            'sentiment_score': 0.0,
            'novelty_score': 0.0,
            'freshness_score': 0.0,
            'priced_in_risk_score': 0.0,
            'summary_text': 'News summary unavailable',
            'headline_count': 0,
            'latest_published_at': None,
        }

    _CACHE[k] = (now, out)
    return out
