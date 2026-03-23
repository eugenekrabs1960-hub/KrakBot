from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import httpx
import json
import re

DATA_DIR = Path(__file__).resolve().parent / "data"
NEWS_STATE_FILE = DATA_DIR / "news_context_state.json"


@dataclass
class NewsSource:
    name: str
    url: str
    weight: float
    tier: str  # official | reuters | coindesk


SOURCES = [
    NewsSource("fed_press", "https://www.federalreserve.gov/feeds/press_all.xml", 1.0, "official"),
    NewsSource("sec_press", "https://www.sec.gov/news/pressreleases.rss", 1.0, "official"),
    NewsSource("reuters_business", "https://feeds.reuters.com/reuters/businessNews", 1.2, "reuters"),
    NewsSource("coindesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", 0.8, "coindesk"),
]

POSITIVE = [
    "approval", "approved", "easing", "cut", "inflow", "adoption", "record high", "bull", "rally", "upgrade",
]
NEGATIVE = [
    "lawsuit", "enforcement", "ban", "hack", "exploit", "outflow", "liquidation", "recession", "crackdown", "default", "tariff",
]
RISK_HIGH = ["hack", "exploit", "ban", "crackdown", "war", "default", "liquidation", "sanction", "emergency"]
TARGET = re.compile(r"\b(bitcoin|btc|ethereum|eth|crypto|digital asset)\b", re.IGNORECASE)
BTC_RE = re.compile(r"\b(bitcoin|btc)\b", re.IGNORECASE)
ETH_RE = re.compile(r"\b(ethereum|eth)\b", re.IGNORECASE)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_items(xml_text: str, source: NewsSource) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return out
    for item in root.findall('.//item')[:20]:
        title = (item.findtext('title') or '').strip()
        link = (item.findtext('link') or '').strip()
        desc = (item.findtext('description') or '').strip()
        text = f"{title} {desc}".lower()
        if not TARGET.search(text):
            continue
        score = 0.0
        for t in POSITIVE:
            if t in text:
                score += 1.0
        for t in NEGATIVE:
            if t in text:
                score -= 1.0
        risk_boost = sum(1 for t in RISK_HIGH if t in text)
        out.append({
            "source": source.name,
            "tier": source.tier,
            "weight": source.weight,
            "title": title,
            "link": link,
            "score": score,
            "risk_boost": risk_boost,
            "btc_hit": bool(BTC_RE.search(text)),
            "eth_hit": bool(ETH_RE.search(text)),
        })
    return out


def _aggregate_slice(items: list[dict[str, Any]], label: str) -> dict[str, Any]:
    if not items:
        return {
            "news_risk": "low",
            "news_bias": "neutral",
            "source_confidence": "low",
            "summary": f"No high-signal {label} headlines detected.",
            "why_it_matters": f"No confirmed {label} catalyst currently detected in this pass.",
        }

    weighted = sum(i["score"] * i["weight"] for i in items)
    risk_score = sum(i["risk_boost"] * i["weight"] for i in items)
    tiers = {i["tier"] for i in items}

    if weighted > 1.5:
        bias = "bullish"
    elif weighted < -1.5:
        bias = "bearish"
    elif abs(weighted) <= 0.75:
        bias = "neutral"
    else:
        bias = "mixed"

    if risk_score >= 6:
        risk = "high"
    elif risk_score >= 2:
        risk = "medium"
    else:
        risk = "low"

    if "official" in tiers and "reuters" in tiers:
        conf = "high"
    elif "reuters" in tiers or "official" in tiers:
        conf = "medium"
    else:
        conf = "low"

    top = sorted(items, key=lambda x: abs(x["score"]) * x["weight"] + x["risk_boost"], reverse=True)[:3]
    summary = "; ".join(i["title"] for i in top if i.get("title"))[:320] or f"Mixed {label} headlines."
    why = f"Bias={bias}, risk={risk}, confidence={conf}, based on {len(items)} relevant headlines across {len(tiers)} source tiers."

    return {
        "news_risk": risk,
        "news_bias": bias,
        "source_confidence": conf,
        "summary": summary,
        "why_it_matters": why,
    }


def aggregate(items: list[dict[str, Any]]) -> dict[str, Any]:
    overall = _aggregate_slice(items, "BTC/ETH")
    btc_items = [i for i in items if i.get("btc_hit")]
    eth_items = [i for i in items if i.get("eth_hit")]
    btc = _aggregate_slice(btc_items, "BTC")
    eth = _aggregate_slice(eth_items, "ETH")

    top = sorted(items, key=lambda x: abs(x["score"]) * x["weight"] + x["risk_boost"], reverse=True)[:3]
    return {
        **overall,
        "btc": {k: btc[k] for k in ["news_risk", "news_bias", "source_confidence"]},
        "eth": {k: eth[k] for k in ["news_risk", "news_bias", "source_confidence"]},
        "summary": overall["summary"],
        "why_it_matters": overall["why_it_matters"],
        "items": top,
    }


async def build_news_context(force_refresh: bool = False, ttl_minutes: int = 20) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if NEWS_STATE_FILE.exists() and not force_refresh:
        try:
            cur = json.loads(NEWS_STATE_FILE.read_text())
            ts = datetime.fromisoformat(str(cur.get("updated_at", "")).replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - ts < timedelta(minutes=ttl_minutes):
                return cur
        except Exception:
            pass

    items: list[dict[str, Any]] = []
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for s in SOURCES:
            try:
                r = await client.get(s.url)
                r.raise_for_status()
                items.extend(parse_items(r.text, s))
            except Exception as e:
                errors.append(f"{s.name}: {type(e).__name__}")

    agg = aggregate(items)
    state = {
        "updated_at": now_iso(),
        "sources": [s.__dict__ for s in SOURCES],
        "headline_count": len(items),
        "errors": errors,
        **agg,
    }
    NEWS_STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")
    return state
