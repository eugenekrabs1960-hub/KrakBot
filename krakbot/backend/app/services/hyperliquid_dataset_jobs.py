from __future__ import annotations

import csv
import time
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

DATA_DIR = Path(__file__).resolve().parents[2] / 'data' / 'training'


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

    rows = db.execute(text(query), params).mappings().all()
    sym = (symbol or 'ALL').replace('/', '_')
    file_path = DATA_DIR / f"hl_features_{sym}_{now_ms}.csv"

    with file_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'ts', 'environment', 'symbol', 'mid_price', 'ret_1', 'ret_5', 'ret_15', 'source'])
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k) for k in writer.fieldnames})

    return {
        'ok': True,
        'path': str(file_path),
        'rows': len(rows),
        'symbol': symbol,
        'from_ts': from_ts,
        'to_ts': to_ts,
        'limit': limit,
    }
