from __future__ import annotations

import json
import math
import time
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

MODEL_DIR = Path(__file__).resolve().parents[2] / 'data' / 'models'


def _load_rows(db: Session, symbol: str, limit: int = 50000):
    rows = db.execute(
        text(
            """
            SELECT ts, symbol, ret_1, ret_5, ret_15, mid_price
            FROM hyperliquid_training_features
            WHERE symbol=:symbol
            ORDER BY ts ASC
            LIMIT :limit
            """
        ),
        {'symbol': symbol, 'limit': max(100, min(200000, int(limit)))},
    ).mappings().all()
    data = [dict(r) for r in rows]
    n = len(data)
    for i in range(n):
        curr = float(data[i].get('mid_price') or 0.0)
        j = i + 5
        data[i]['y_ret_fwd_5'] = None if j >= n or curr == 0 else (float(data[j]['mid_price']) - curr) / curr
    return data


def _metrics(y_true: list[int], y_pred: list[int]):
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)
    total = max(1, len(y_true))
    acc = (tp + tn) / total
    precision = tp / max(1, (tp + fp))
    recall = tp / max(1, (tp + fn))
    return {'accuracy': acc, 'precision': precision, 'recall': recall, 'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn}


def train_baseline(db: Session, symbol: str = 'BTC', limit: int = 50000):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    rows = _load_rows(db, symbol, limit=limit)
    rows = [r for r in rows if r.get('y_ret_fwd_5') is not None and r.get('ret_1') is not None]
    if len(rows) < 30:
        return {'ok': False, 'error': 'not_enough_data', 'rows': len(rows)}

    split = max(20, int(len(rows) * 0.7))
    train = rows[:split]
    test = rows[split:]

    # simple baseline: predict long when ret_1 > threshold determined on train median
    vals = sorted(float(r.get('ret_1') or 0.0) for r in train)
    thr = vals[len(vals) // 2]

    y_true = [1 if float(r['y_ret_fwd_5']) > 0 else 0 for r in test]
    y_pred = [1 if float(r.get('ret_1') or 0.0) > thr else 0 for r in test]
    m = _metrics(y_true, y_pred)

    ev = 0.0
    for r, p in zip(test, y_pred):
        ret = float(r['y_ret_fwd_5'])
        if p == 1:
            ev += ret
        else:
            ev += -ret
    m['avg_strategy_return_proxy'] = ev / max(1, len(test))

    now = int(time.time() * 1000)
    artifact = {
        'model_type': 'baseline_threshold_ret1',
        'symbol': symbol,
        'created_at_ms': now,
        'threshold_ret1': thr,
        'train_rows': len(train),
        'test_rows': len(test),
        'metrics': m,
        'feature_schema': ['ret_1', 'ret_5', 'ret_15'],
        'label': 'y_ret_fwd_5',
    }
    path = MODEL_DIR / f'model_{symbol}_{now}.json'
    path.write_text(json.dumps(artifact, indent=2), encoding='utf-8')

    return {'ok': True, 'artifact_path': str(path), **artifact}


def latest_model(symbol: str = 'BTC'):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(MODEL_DIR.glob(f'model_{symbol}_*.json'))
    if not files:
        return {'ok': False, 'error': 'model_not_found'}
    data = json.loads(files[-1].read_text(encoding='utf-8'))
    return {'ok': True, 'item': data, 'path': str(files[-1])}


def strategy_benchmarks(db: Session, symbol: str = 'BTC', limit: int = 50000):
    rows = _load_rows(db, symbol=symbol, limit=limit)
    rows = [r for r in rows if r.get('y_ret_fwd_5') is not None and r.get('ret_1') is not None and r.get('ret_5') is not None]
    if not rows:
        return {'ok': True, 'items': []}

    def run(name, fn):
        pnl = 0.0
        wins = 0
        trades = 0
        for r in rows:
            pos = fn(r)
            if pos == 0:
                continue
            trades += 1
            ret = float(r['y_ret_fwd_5'])
            pnl += pos * ret
            if pos * ret > 0:
                wins += 1
        return {
            'name': name,
            'trades': trades,
            'win_rate': (wins / trades * 100.0) if trades else 0.0,
            'pnl_proxy': pnl,
            'avg_ret_proxy': pnl / trades if trades else 0.0,
        }

    items = [
        run('Momentum-1m', lambda r: 1 if float(r['ret_1']) > 0 else -1),
        run('Mean-Reversion-5m', lambda r: -1 if float(r['ret_5']) > 0 else 1),
        run('Trend-Blend', lambda r: 1 if (float(r['ret_1']) + float(r['ret_5'])) > 0 else -1),
    ]
    return {'ok': True, 'items': items}
