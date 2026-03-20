from __future__ import annotations

import copy
import time
from datetime import datetime, timezone
import uuid
from collections import Counter

from sqlalchemy.orm import Session

from app.api import models as api_models
from app.core.config import settings
from app.models.db_models import ExperimentRunDB
from app.services.decision_engine import run_decision_cycle
from app.services.paper_account import compute_paper_account_from_exec
from app.services.paper_reset import reset_paper_state
from app.models.db_models import ExecutionRecordDB


def _set_nested(obj, path: str, value):
    parts = path.split('.')
    cur = obj
    for p in parts[:-1]:
        cur = getattr(cur, p)
    setattr(cur, parts[-1], value)


def _get_nested(obj, path: str):
    cur = obj
    for p in path.split('.'):
        cur = getattr(cur, p)
    return cur


def _bucket_conf(c: float) -> str:
    if c < 0.4:
        return '0.00-0.39'
    if c < 0.6:
        return '0.40-0.59'
    if c < 0.8:
        return '0.60-0.79'
    return '0.80-1.00'


def _run_window(db: Session, cycles: int) -> dict:
    policy = Counter()
    by_coin = Counter()
    by_side = Counter()
    by_setup = Counter()
    by_conf = Counter()
    fills = 0
    fees = 0.0
    lats = []

    for _ in range(cycles):
        t0 = time.time()
        out = run_decision_cycle(db)
        lats.append((time.time() - t0) * 1000)
        for it in out.get('items', []):
            d = it.get('decision', {})
            p = it.get('policy', {})
            e = it.get('execution') or {}
            pol = p.get('final_action', 'unknown')
            policy[pol] += 1
            by_coin[f"{d.get('coin', '?')}:{pol}"] += 1
            by_side[d.get('action', 'unknown')] += 1
            by_setup[d.get('setup_type', 'unknown')] += 1
            by_conf[_bucket_conf(float(d.get('confidence') or 0.0))] += 1
            if e.get('status') == 'filled':
                fills += 1
                fees += float(e.get('fee_usd') or 0.0)

    exec_rows = [r.payload for r in db.query(ExecutionRecordDB).filter(ExecutionRecordDB.mode == 'paper').all()]
    acct = compute_paper_account_from_exec(exec_rows)

    return {
        'cycles': cycles,
        'policy_outcomes': dict(policy),
        'by_coin_policy': dict(by_coin),
        'by_side_action': dict(by_side),
        'by_setup_type': dict(by_setup),
        'by_conf_bucket': dict(by_conf),
        'fills': fills,
        'fees_usd': fees,
        'paper_account': acct,
        'latency_ms': {
            'min': min(lats) if lats else None,
            'mean': (sum(lats) / len(lats)) if lats else None,
            'max': max(lats) if lats else None,
        },
    }


def _classify(base: dict, var: dict) -> str:
    b = float(base.get('paper_account', {}).get('total_equity_usd') or 0.0)
    v = float(var.get('paper_account', {}).get('total_equity_usd') or 0.0)
    delta = v - b
    if delta > 5:
        return 'keep'
    if delta < -5:
        return 'reject'
    return 'inconclusive'


def run_experiment(db: Session, *, name: str, change_path: str, change_value, cycles: int = 40) -> dict:
    if api_models.runtime_settings.mode.execution_mode != 'paper':
        raise ValueError('paper_only_experiments')
    if cycles < 5 or cycles > 200:
        raise ValueError('cycles_out_of_bounds')

    run_id = f"exp_{uuid.uuid4().hex[:10]}"
    settings_before = copy.deepcopy(api_models.runtime_settings)

    baseline_reset = reset_paper_state(db)
    baseline = _run_window(db, cycles)

    reset_paper_state(db)
    old_value = _get_nested(api_models.runtime_settings, change_path)
    _set_nested(api_models.runtime_settings, change_path, change_value)
    variant = _run_window(db, cycles)

    _set_nested(api_models.runtime_settings, change_path, old_value)

    result = {
        'run_id': run_id,
        'name': name,
        'spec': {
            'paper_only': True,
            'one_change': {'path': change_path, 'old': old_value, 'new': change_value},
            'cycles': cycles,
            'baseline_starting_equity_usd': settings.paper_starting_equity_usd,
        },
        'settings_snapshot_before': settings_before.model_dump(),
        'baseline_reset': baseline_reset,
        'baseline_metrics': baseline,
        'variant_metrics': variant,
        'classification': _classify(baseline, variant),
    }

    db.add(ExperimentRunDB(
        run_id=run_id,
        name=name,
        status='completed',
        created_at=datetime.now(timezone.utc),
        payload=result,
    ))
    db.commit()
    return result
