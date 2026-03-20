from __future__ import annotations

import requests
from app.core.config import settings


HL_INFO_URL = "https://api.hyperliquid.xyz/info"


def _post_info(payload: dict) -> dict | list:
    r = requests.post(HL_INFO_URL, json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


def fetch_market_snapshot(coin: str) -> dict:
    """Public-data ingest for Hyperliquid market snapshot.

    Falls back to synthetic values only if public endpoint errors.
    """
    try:
        if not settings.external_api_enabled:
            raise RuntimeError("external_api_disabled")
        meta_ctx = _post_info({"type": "metaAndAssetCtxs"})
        universe = meta_ctx[0]["universe"]
        ctxs = meta_ctx[1]

        idx = next((i for i, a in enumerate(universe) if a.get("name") == coin), None)
        if idx is None:
            raise ValueError(f"coin {coin} not found in Hyperliquid universe")

        ctx = ctxs[idx]
        mark = float(ctx.get("markPx") or 0.0)
        mid = float(ctx.get("midPx") or mark or 0.0)
        oracle = float(ctx.get("oraclePx") or mark or 0.0)
        funding = float(ctx.get("funding") or 0.0)
        oi = float(ctx.get("openInterest") or 0.0)
        day_ntl = float(ctx.get("dayNtlVlm") or 0.0)

        spread_bps = abs(mid - mark) / mark * 10000 if mark else 0.0
        volume_1h = day_ntl / 24.0 if day_ntl else 0.0
        volume_5m = volume_1h / 12.0 if volume_1h else 0.0

        return {
            "coin": coin,
            "symbol": f"{coin}-PERP",
            "last_price": mid,
            "mark_price": mark,
            "index_price": oracle,
            "spread_bps": spread_bps,
            "volume_5m_usd": volume_5m,
            "volume_1h_usd": volume_1h,
            "open_interest_usd": oi * mark,
            "funding_rate": funding,
            "source": "hyperliquid_public",
        }
    except Exception:
        # safe fallback for continuity in local dev
        px = 1000.0
        return {
            "coin": coin,
            "symbol": f"{coin}-PERP",
            "last_price": px,
            "mark_price": px,
            "index_price": px,
            "spread_bps": 8.0,
            "volume_5m_usd": 500000.0,
            "volume_1h_usd": 8000000.0,
            "open_interest_usd": 60000000.0,
            "funding_rate": 0.0,
            "source": "fallback",
        }
