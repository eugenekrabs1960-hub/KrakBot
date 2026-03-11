from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

DATA_DIR = Path(__file__).resolve().parents[2] / 'data' / 'training'
SCHEMA_VERSION = 'hl_dataset_v1'


def _dataset_path(prefix: str, symbol: str | None, now_ms: int) -> Path:
    sym = (symbol or 'ALL').replace('/', '_')
    return DATA_DIR / f"{prefix}_{sym}_{now_ms}.csv"


def _manifest_path(prefix: str, symbol: str | None, now_ms: int) -> Path:
    sym = (symbol or 'ALL').replace('/', '_')
    return DATA_DIR / f"{prefix}_{sym}_{now_ms}.manifest.json"


def _write_manifest(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def _query_training_rows(db: Session, *, symbol: str | None, from_ts: int | None, to_ts: int | None, limit: int):
    where = ["1=1"]
    params: dict = {'limit': max(1, min(200000, int(limit)))}
    if symbol:
        where.append("symbol=:symbol")
        params['symbol'] = symbol
    if from_ts is not None:
        where.append("ts>=:from_ts")
        params['from_ts'] = int(from_ts)
    if to_ts is not None:
        where.append("ts<=:to_ts")
        params['to_ts'] = int(to_ts)

    query = f"""
        SELECT id, ts, environment, symbol, mid_price, ret_1, ret_5, ret_15, source
        FROM hyperliquid_training_features
        WHERE {' AND '.join(where)}
        ORDER BY ts DESC, id DESC
        LIMIT :limit
    """
    return db.execute(text(query), params).mappings().all(), params


def export_training_dataset_csv(
    db: Session,
    *,
    symbol: str | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    limit: int = 20000,
) -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    now_ms = int(time.time() * 1000)

    rows, params = _query_training_rows(db, symbol=symbol, from_ts=from_ts, to_ts=to_ts, limit=limit)
    file_path = _dataset_path('hl_features', symbol, now_ms)

    fieldnames = ['id', 'ts', 'environment', 'symbol', 'mid_price', 'ret_1', 'ret_5', 'ret_15', 'source']
    with file_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k) for k in fieldnames})

    dataset_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
    manifest = {
        'schema_version': SCHEMA_VERSION,
        'kind': 'features_only',
        'created_at_ms': now_ms,
        'rows': len(rows),
        'params': {'symbol': symbol, 'from_ts': from_ts, 'to_ts': to_ts, 'limit': limit, **params},
        'dataset_hash_sha256': dataset_hash,
        'file_path': str(file_path),
    }
    mpath = _manifest_path('hl_features', symbol, now_ms)
    _write_manifest(mpath, manifest)

    return {
        'ok': True,
        'path': str(file_path),
        'manifest_path': str(mpath),
        'rows': len(rows),
        'symbol': symbol,
        'from_ts': from_ts,
        'to_ts': to_ts,
        'limit': limit,
        'dataset_hash_sha256': dataset_hash,
    }


def build_labeled_dataset_v1(
    db: Session,
    *,
    symbol: str,
    from_ts: int | None = None,
    to_ts: int | None = None,
    limit: int = 50000,
) -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    now_ms = int(time.time() * 1000)

    where = ["symbol=:symbol"]
    params: dict = {'symbol': symbol, 'limit': max(1, min(200000, int(limit)))}
    if from_ts is not None:
        where.append("ts>=:from_ts")
        params['from_ts'] = int(from_ts)
    if to_ts is not None:
        where.append("ts<=:to_ts")
        params['to_ts'] = int(to_ts)

    rows = db.execute(
        text(
            f"""
            SELECT ts, environment, symbol, mid_price, ret_1, ret_5, ret_15
            FROM hyperliquid_training_features
            WHERE {' AND '.join(where)}
            ORDER BY ts ASC
            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()

    # Leakage-safe labels: y is computed from strictly future timestamps.
    data = [dict(r) for r in rows]
    n = len(data)
    for i in range(n):
        curr = float(data[i]['mid_price'] or 0.0)
        for h in (5, 15, 60):
            j = i + h
            key = f'y_ret_fwd_{h}'
            if curr == 0 or j >= n:
                data[i][key] = None
            else:
                nxt = float(data[j]['mid_price'] or 0.0)
                data[i][key] = (nxt - curr) / curr

    file_path = _dataset_path('hl_labeled_v1', symbol, now_ms)
    fieldnames = ['ts', 'environment', 'symbol', 'mid_price', 'ret_1', 'ret_5', 'ret_15', 'y_ret_fwd_5', 'y_ret_fwd_15', 'y_ret_fwd_60']
    with file_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in data:
            writer.writerow({k: r.get(k) for k in fieldnames})

    dataset_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
    manifest = {
        'schema_version': SCHEMA_VERSION,
        'kind': 'labeled_v1',
        'created_at_ms': now_ms,
        'rows': len(data),
        'symbol': symbol,
        'from_ts': from_ts,
        'to_ts': to_ts,
        'limit': limit,
        'label_horizons': [5, 15, 60],
        'leakage_guard': 'labels derived from future rows only (i+h)',
        'dataset_hash_sha256': dataset_hash,
        'file_path': str(file_path),
    }
    mpath = _manifest_path('hl_labeled_v1', symbol, now_ms)
    _write_manifest(mpath, manifest)

    return {
        'ok': True,
        'path': str(file_path),
        'manifest_path': str(mpath),
        'rows': len(data),
        'symbol': symbol,
        'dataset_hash_sha256': dataset_hash,
    }
