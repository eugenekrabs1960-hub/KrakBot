from __future__ import annotations

import json
import time
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

MODEL_DIR = Path(__file__).resolve().parents[2] / 'data' / 'models'
JOB_LOG_PATH = MODEL_DIR / 'model_lab_jobs.jsonl'


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


def _append_job_log(entry: dict):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with JOB_LOG_PATH.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry) + "\n")


def list_job_history(limit: int = 50):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if not JOB_LOG_PATH.exists():
        return {'ok': True, 'items': []}
    lines = JOB_LOG_PATH.read_text(encoding='utf-8').splitlines()
    items = []
    for line in lines[-max(1, min(1000, int(limit))):]:
        try:
            items.append(json.loads(line))
        except Exception:
            continue
    items.reverse()
    return {'ok': True, 'items': items}


def set_active_model_for_paper(db: Session, *, symbol: str, model_path: str, confirm_phrase: str):
    if confirm_phrase != 'PROMOTE':
        return {'ok': False, 'error': 'confirmation_required', 'required': 'PROMOTE'}

    payload_obj = {'symbol': symbol, 'model_path': model_path, 'promoted_at_ms': int(time.time() * 1000)}
    payload = json.dumps(payload_obj)

    dialect = getattr(getattr(db, 'bind', None), 'dialect', None)
    dialect_name = getattr(dialect, 'name', '')
    if dialect_name == 'postgresql':
        db.execute(
            text(
                """
                INSERT INTO system_state(key, value, updated_at)
                VALUES ('model_lab_active_paper', CAST(:payload AS jsonb), CURRENT_TIMESTAMP)
                ON CONFLICT (key)
                DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                """
            ),
            {'payload': payload},
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO system_state(key, value, updated_at)
                VALUES ('model_lab_active_paper', :payload, CURRENT_TIMESTAMP)
                ON CONFLICT (key)
                DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                """
            ),
            {'payload': payload},
        )
    db.commit()
    return {'ok': True, 'item': payload_obj}


def get_active_model_for_paper(db: Session):
    row = db.execute(text("SELECT value FROM system_state WHERE key='model_lab_active_paper' LIMIT 1")).mappings().first()
    if not row:
        return {'ok': True, 'item': None}
    value = row.get('value')
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            value = None
    return {'ok': True, 'item': value}


def set_active_execution_model(db: Session, *, agent_id: str, confirm_phrase: str):
    if confirm_phrase != 'SWITCH':
        return {'ok': False, 'error': 'confirmation_required', 'required': 'SWITCH'}

    payload_obj = {'agent_id': agent_id, 'selected_at_ms': int(time.time() * 1000)}
    payload = json.dumps(payload_obj)

    dialect = getattr(getattr(db, 'bind', None), 'dialect', None)
    dialect_name = getattr(dialect, 'name', '')
    if dialect_name == 'postgresql':
        db.execute(
            text(
                """
                INSERT INTO system_state(key, value, updated_at)
                VALUES ('model_arena_active_execution', CAST(:payload AS jsonb), CURRENT_TIMESTAMP)
                ON CONFLICT (key)
                DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                """
            ),
            {'payload': payload},
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO system_state(key, value, updated_at)
                VALUES ('model_arena_active_execution', :payload, CURRENT_TIMESTAMP)
                ON CONFLICT (key)
                DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                """
            ),
            {'payload': payload},
        )
    db.commit()
    return {'ok': True, 'item': payload_obj}


def get_active_execution_model(db: Session):
    row = db.execute(text("SELECT value FROM system_state WHERE key='model_arena_active_execution' LIMIT 1")).mappings().first()
    if not row:
        return {'ok': True, 'item': None}
    value = row.get('value')
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            value = None
    return {'ok': True, 'item': value}


def train_baseline(db: Session, symbol: str = 'BTC', limit: int = 50000):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    started_at = int(time.time() * 1000)
    rows = _load_rows(db, symbol, limit=limit)
    rows = [r for r in rows if r.get('y_ret_fwd_5') is not None and r.get('ret_1') is not None]
    if len(rows) < 30:
        out = {'ok': False, 'error': 'not_enough_data', 'rows': len(rows)}
        _append_job_log({'kind': 'train_baseline', 'symbol': symbol, 'started_at_ms': started_at, 'finished_at_ms': int(time.time() * 1000), **out})
        return out

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

    out = {'ok': True, 'artifact_path': str(path), **artifact}
    _append_job_log({'kind': 'train_baseline', 'symbol': symbol, 'started_at_ms': started_at, 'finished_at_ms': int(time.time() * 1000), 'ok': True, 'artifact_path': str(path), 'metrics': m})
    return out


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
