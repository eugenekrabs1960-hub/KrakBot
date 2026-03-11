from __future__ import annotations

import json
import time
from dataclasses import dataclass

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings


@dataclass
class CollectResult:
    ok: bool
    ts: int
    mids_written: int
    features_written: int
    symbols_count: int


@dataclass
class BackfillResult:
    ok: bool
    symbol: str
    interval: str
    start_time_ms: int
    end_time_ms: int
    candles_received: int
    mids_written: int
    features_written: int


class HyperliquidMarketDataService:
    def __init__(self, base_url: str | None = None, environment: str | None = None, post=None):
        self.base_url = (base_url or settings.hyperliquid_base_url).rstrip('/')
        self.environment = environment or settings.hyperliquid_environment
        self._post = post or requests.post

    def _info(self, payload: dict):
        resp = self._post(f'{self.base_url}/info', json=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def collect_once(self, db: Session, *, symbols_limit: int = 120) -> CollectResult:
        now_ms = int(time.time() * 1000)
        mids = self._info({'type': 'allMids'})
        meta = self._info({'type': 'meta'})

        if not isinstance(mids, dict):
            mids = {}

        selected = [(k, float(v)) for k, v in mids.items() if isinstance(v, (int, float, str))]
        selected.sort(key=lambda kv: kv[0])
        selected = selected[: max(1, min(1000, symbols_limit))]

        for symbol, mid in selected:
            db.execute(
                text(
                    """
                    INSERT INTO hyperliquid_market_mids(ts, environment, symbol, mid_price)
                    VALUES (:ts, :environment, :symbol, :mid_price)
                    """
                ),
                {'ts': now_ms, 'environment': self.environment, 'symbol': symbol, 'mid_price': float(mid)},
            )

        payload_json = json.dumps(meta if isinstance(meta, dict) else {})
        try:
            db.execute(
                text(
                    """
                    INSERT INTO hyperliquid_market_meta_snapshots(ts, environment, symbols_count, payload_json)
                    VALUES (:ts, :environment, :symbols_count, CAST(:payload_json AS jsonb))
                    """
                ),
                {
                    'ts': now_ms,
                    'environment': self.environment,
                    'symbols_count': len(meta.get('universe') or []) if isinstance(meta, dict) else 0,
                    'payload_json': payload_json,
                },
            )
        except Exception:
            db.rollback()
            db.execute(
                text(
                    """
                    INSERT INTO hyperliquid_market_meta_snapshots(ts, environment, symbols_count, payload_json)
                    VALUES (:ts, :environment, :symbols_count, :payload_json)
                    """
                ),
                {
                    'ts': now_ms,
                    'environment': self.environment,
                    'symbols_count': len(meta.get('universe') or []) if isinstance(meta, dict) else 0,
                    'payload_json': payload_json,
                },
            )
        db.commit()

        features_written = self._compute_feature_rows(db, ts=now_ms, symbols=[s for s, _ in selected], source='hyperliquid_public_v1')
        return CollectResult(
            ok=True,
            ts=now_ms,
            mids_written=len(selected),
            features_written=features_written,
            symbols_count=len(meta.get('universe') or []) if isinstance(meta, dict) else 0,
        )

    def backfill_candles(
        self,
        db: Session,
        *,
        symbol: str,
        interval: str = '1m',
        start_time_ms: int,
        end_time_ms: int,
    ) -> BackfillResult:
        req = {
            'type': 'candleSnapshot',
            'req': {
                'coin': symbol,
                'interval': interval,
                'startTime': int(start_time_ms),
                'endTime': int(end_time_ms),
            },
        }
        data = self._info(req)
        candles = data if isinstance(data, list) else []

        parsed: list[tuple[int, float]] = []
        mids_written = 0
        for c in candles:
            ts = int(c.get('t') or c.get('time') or c.get('T') or 0)
            close = c.get('c')
            if not ts or close is None:
                continue
            try:
                mid_price = float(close)
            except Exception:
                continue
            parsed.append((ts, mid_price))
            db.execute(
                text(
                    """
                    INSERT INTO hyperliquid_market_mids(ts, environment, symbol, mid_price)
                    VALUES (:ts, :environment, :symbol, :mid_price)
                    """
                ),
                {'ts': ts, 'environment': self.environment, 'symbol': symbol, 'mid_price': mid_price},
            )
            mids_written += 1
        db.commit()

        # Generate feature rows for each backfilled timestamp, leakage-safe by using only prior points.
        parsed.sort(key=lambda x: x[0])
        features_written = 0
        n = len(parsed)
        for i in range(n):
            ts, curr = parsed[i]

            def ret_at(k: int):
                j = i - k
                if j < 0:
                    return None
                prev = parsed[j][1]
                if prev == 0:
                    return None
                return (curr - prev) / prev

            db.execute(
                text(
                    """
                    INSERT INTO hyperliquid_training_features(
                      ts, environment, symbol, mid_price, ret_1, ret_5, ret_15, source
                    )
                    VALUES (
                      :ts, :environment, :symbol, :mid_price, :ret_1, :ret_5, :ret_15, :source
                    )
                    """
                ),
                {
                    'ts': ts,
                    'environment': self.environment,
                    'symbol': symbol,
                    'mid_price': curr,
                    'ret_1': ret_at(1),
                    'ret_5': ret_at(5),
                    'ret_15': ret_at(15),
                    'source': 'hyperliquid_backfill_v1',
                },
            )
            features_written += 1
        db.commit()

        return BackfillResult(
            ok=True,
            symbol=symbol,
            interval=interval,
            start_time_ms=int(start_time_ms),
            end_time_ms=int(end_time_ms),
            candles_received=len(candles),
            mids_written=mids_written,
            features_written=features_written,
        )

    def _compute_feature_rows(self, db: Session, *, ts: int | None, symbols: list[str], source: str = 'hyperliquid_public_v1') -> int:
        written = 0
        for s in symbols:
            rows = db.execute(
                text(
                    """
                    SELECT ts, mid_price
                    FROM hyperliquid_market_mids
                    WHERE symbol=:symbol
                    ORDER BY ts DESC
                    LIMIT 16
                    """
                ),
                {'symbol': s},
            ).mappings().all()
            if not rows:
                continue

            curr = float(rows[0]['mid_price'])

            def ret_at(idx: int):
                if len(rows) <= idx:
                    return None
                prev = float(rows[idx]['mid_price'])
                if prev == 0:
                    return None
                return (curr - prev) / prev

            write_ts = int(rows[0]['ts']) if ts is None else int(ts)
            db.execute(
                text(
                    """
                    INSERT INTO hyperliquid_training_features(
                      ts, environment, symbol, mid_price, ret_1, ret_5, ret_15, source
                    )
                    VALUES (
                      :ts, :environment, :symbol, :mid_price, :ret_1, :ret_5, :ret_15, :source
                    )
                    """
                ),
                {
                    'ts': write_ts,
                    'environment': self.environment,
                    'symbol': s,
                    'mid_price': curr,
                    'ret_1': ret_at(1),
                    'ret_5': ret_at(5),
                    'ret_15': ret_at(15),
                    'source': source,
                },
            )
            written += 1

        db.commit()
        return written


def list_latest_training_features(db: Session, limit: int = 200, symbol: str | None = None):
    try:
        if symbol:
            rows = db.execute(
                text(
                    """
                    SELECT id, ts, environment, symbol, mid_price, ret_1, ret_5, ret_15, source
                    FROM hyperliquid_training_features
                    WHERE symbol=:symbol
                    ORDER BY id DESC
                    LIMIT :limit
                    """
                ),
                {'symbol': symbol, 'limit': max(1, min(5000, int(limit)))},
            ).mappings().all()
        else:
            rows = db.execute(
                text(
                    """
                    SELECT id, ts, environment, symbol, mid_price, ret_1, ret_5, ret_15, source
                    FROM hyperliquid_training_features
                    ORDER BY id DESC
                    LIMIT :limit
                    """
                ),
                {'limit': max(1, min(5000, int(limit)))},
            ).mappings().all()
        return [dict(r) for r in rows]
    except Exception:
        return []
