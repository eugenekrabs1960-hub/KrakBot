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

        features_written = self._compute_feature_rows(db, ts=now_ms, symbols=[s for s, _ in selected])
        return CollectResult(
            ok=True,
            ts=now_ms,
            mids_written=len(selected),
            features_written=features_written,
            symbols_count=len(meta.get('universe') or []) if isinstance(meta, dict) else 0,
        )

    def _compute_feature_rows(self, db: Session, *, ts: int, symbols: list[str]) -> int:
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

            db.execute(
                text(
                    """
                    INSERT INTO hyperliquid_training_features(
                      ts, environment, symbol, mid_price, ret_1, ret_5, ret_15, source
                    )
                    VALUES (
                      :ts, :environment, :symbol, :mid_price, :ret_1, :ret_5, :ret_15, 'hyperliquid_public_v1'
                    )
                    """
                ),
                {
                    'ts': ts,
                    'environment': self.environment,
                    'symbol': s,
                    'mid_price': curr,
                    'ret_1': ret_at(1),
                    'ret_5': ret_at(5),
                    'ret_15': ret_at(15),
                },
            )
            written += 1

        db.commit()
        return written


def list_latest_training_features(db: Session, limit: int = 200, symbol: str | None = None):
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
