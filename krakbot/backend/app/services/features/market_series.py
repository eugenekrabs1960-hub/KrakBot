from __future__ import annotations

from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.models.db_models import MarketSnapshot1mDB


def persist_market_snapshot(db: Session, market: dict) -> None:
    row = MarketSnapshot1mDB(
        ts=datetime.now(timezone.utc),
        coin=market.get('coin') or market.get('symbol','UNK').replace('-PERP',''),
        symbol=market.get('symbol') or 'UNK-PERP',
        mid_price=float(market.get('last_price') or 0.0),
        mark_price=float(market.get('mark_price') or 0.0),
        index_price=float(market.get('index_price') or 0.0),
        spread_bps=float(market.get('spread_bps') or 0.0),
        funding_rate=float(market.get('funding_rate') or 0.0),
        open_interest_usd=float(market.get('open_interest_usd') or 0.0),
        volume_5m_usd=float(market.get('volume_5m_usd') or 0.0),
        volume_1h_usd=float(market.get('volume_1h_usd') or 0.0),
        source=str(market.get('source') or 'unknown'),
    )
    db.add(row)


def load_market_series(db: Session, coin: str, lookback_hours: int = 6) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    rows = (
        db.query(MarketSnapshot1mDB)
        .filter(MarketSnapshot1mDB.coin == coin, MarketSnapshot1mDB.ts >= since)
        .order_by(MarketSnapshot1mDB.ts.asc())
        .all()
    )
    return [
        {
            'ts': r.ts,
            'px': float(r.mark_price or r.mid_price or 0.0),
            'vol5': float(r.volume_5m_usd or 0.0),
            'oi': float(r.open_interest_usd or 0.0),
            'funding': float(r.funding_rate or 0.0),
        }
        for r in rows
    ]


import requests
from app.core.config import settings

_HL_INFO_URL = "https://api.hyperliquid.xyz/info"
_SEED_STATE: dict[str, dict] = {}


def get_seed_state(coin: str) -> dict:
    return _SEED_STATE.get(coin, {
        'seeded': False,
        'source': 'hyperliquid_candle_snapshot',
        'lookback_minutes': int(settings.trading_history_seed_lookback_minutes),
        'points_loaded': 0,
        'min_points_required': int(settings.trading_history_seed_min_points),
        'approximation_flags': [],
        'degraded_reason': 'not_seeded',
    })


def ensure_hyperliquid_history_seed(db: Session, coin: str, lookback_minutes: int | None = None) -> dict:
    lookback = int(lookback_minutes or settings.trading_history_seed_lookback_minutes)
    min_points = int(settings.trading_history_seed_min_points)
    now = datetime.now(timezone.utc)

    since = now - timedelta(minutes=lookback)
    existing = (
        db.query(MarketSnapshot1mDB)
        .filter(MarketSnapshot1mDB.coin == coin, MarketSnapshot1mDB.ts >= since)
        .count()
    )
    if existing >= min_points:
        state = {
            'seeded': True,
            'source': 'hyperliquid_candle_snapshot',
            'lookback_minutes': lookback,
            'points_loaded': int(existing),
            'min_points_required': min_points,
            'approximation_flags': ['volume_5m_derived_from_candle_volume', 'open_interest_from_live_ctx_not_candle'],
            'degraded_reason': None,
        }
        _SEED_STATE[coin] = state
        return state

    end_ms = int(now.timestamp() * 1000)
    start_ms = int((now - timedelta(minutes=lookback)).timestamp() * 1000)
    payload = {
        'type': 'candleSnapshot',
        'req': {
            'coin': coin,
            'interval': '1m',
            'startTime': start_ms,
            'endTime': end_ms,
        },
    }
    try:
        r = requests.post(_HL_INFO_URL, json=payload, timeout=12)
        r.raise_for_status()
        candles = r.json() if isinstance(r.json(), list) else []

        # get latest funding/oi from official live public ctx
        meta_ctx = requests.post(_HL_INFO_URL, json={'type': 'metaAndAssetCtxs'}, timeout=10)
        meta_ctx.raise_for_status()
        mc = meta_ctx.json()
        universe = (mc[0] or {}).get('universe', []) if isinstance(mc, list) and len(mc) > 1 else []
        ctxs = mc[1] if isinstance(mc, list) and len(mc) > 1 else []
        idx = next((i for i,a in enumerate(universe) if a.get('name') == coin), None)
        ctx = ctxs[idx] if idx is not None and idx < len(ctxs) else {}
        funding = float((ctx or {}).get('funding') or 0.0)
        mark = float((ctx or {}).get('markPx') or 0.0)
        oi = float((ctx or {}).get('openInterest') or 0.0)

        written = 0
        for c in candles:
            ts_ms = int(c.get('t') or c.get('T') or 0)
            close = float(c.get('c') or 0.0)
            vol = float(c.get('v') or 0.0)
            if ts_ms <= 0 or close <= 0:
                continue
            row = MarketSnapshot1mDB(
                ts=datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc),
                coin=coin,
                symbol=f'{coin}-PERP',
                mid_price=close,
                mark_price=close,
                index_price=close,
                spread_bps=0.0,
                funding_rate=funding,
                open_interest_usd=(oi * mark) if mark > 0 else 0.0,
                volume_5m_usd=vol,
                volume_1h_usd=vol * 12.0,
                source='hyperliquid_candle_1m',
            )
            db.merge(row)
            written += 1
        db.commit()

        total = (
            db.query(MarketSnapshot1mDB)
            .filter(MarketSnapshot1mDB.coin == coin, MarketSnapshot1mDB.ts >= since)
            .count()
        )
        seeded = total >= min_points
        state = {
            'seeded': bool(seeded),
            'source': 'hyperliquid_candle_snapshot',
            'lookback_minutes': lookback,
            'points_loaded': int(total),
            'min_points_required': min_points,
            'approximation_flags': ['spread_bps_not_in_candles_set_to_0', 'volume_5m_uses_candle_v_proxy', 'open_interest_from_live_ctx_not_historical'],
            'degraded_reason': None if seeded else 'insufficient_hyperliquid_1m_history',
        }
        _SEED_STATE[coin] = state
        return state
    except Exception as e:
        state = {
            'seeded': False,
            'source': 'hyperliquid_candle_snapshot',
            'lookback_minutes': lookback,
            'points_loaded': int(existing),
            'min_points_required': min_points,
            'approximation_flags': [],
            'degraded_reason': f'hyperliquid_seed_failed:{type(e).__name__}',
        }
        _SEED_STATE[coin] = state
        return state
