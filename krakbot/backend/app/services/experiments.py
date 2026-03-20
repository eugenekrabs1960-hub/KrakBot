from __future__ import annotations

import copy
import time
from datetime import datetime, timezone
import uuid
from collections import Counter

from sqlalchemy.orm import Session

from app.api import models as api_models
from app.core.config import settings
from app.models.db_models import ExperimentRunDB, ExecutionRecordDB
from app.services.decision_engine import run_decision_cycle
from app.services.paper_account import compute_paper_account_from_exec
from app.services.paper_reset import reset_paper_state


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


def _run_window(db: Session, cycles: int, label: str) -> dict:
    policy = Counter()
    by_coin = Counter()
    by_side = Counter()
    by_setup = Counter()
    by_conf = Counter()
    block_reasons = Counter()
    fills = 0
    fees = 0.0
    lats = []

    started_at = datetime.now(timezone.utc)
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
            if str(pol).startswith('block_'):
                block_reasons[p.get('downgrade_or_block_reason') or 'unspecified'] += 1
            if e.get('status') == 'filled':
                fills += 1
                fees += float(e.get('fee_usd') or 0.0)
    ended_at = datetime.now(timezone.utc)

    exec_rows = [r.payload for r in db.query(ExecutionRecordDB).filter(ExecutionRecordDB.mode == 'paper').all()]
    acct = compute_paper_account_from_exec(exec_rows)

    return {
        'label': label,
        'cycles': cycles,
        'market_time_window': {
            'started_at_utc': started_at.isoformat(),
            'ended_at_utc': ended_at.isoformat(),
            'sequential_live_market_note': 'window executed sequentially in real market time; not parallelized',
        },
        'policy_outcomes': dict(policy),
        'summary': {
            'fill_count': fills,
            'fee_total_usd': fees,
            'block_reasons': dict(block_reasons),
            'setup_distribution': dict(by_setup),
            'confidence_distribution': dict(by_conf),
        },
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


def _total_equity(metrics: dict) -> float:
    return float(metrics.get('paper_account', {}).get('total_equity_usd') or 0.0)


def _classify(base: dict, var: dict, control: dict | None) -> str:
    b = _total_equity(base)
    v = _total_equity(var)
    c = _total_equity(control) if control else b
    # keep only when variant outperforms both baseline and control by margin
    if (v - max(b, c)) > 5:
        return 'keep'
    if (v - min(b, c)) < -5:
        return 'reject'
    return 'inconclusive'


def run_experiment(db: Session, *, name: str, change_path: str, change_value, cycles: int = 40, include_control_rerun: bool = False) -> dict:
    if api_models.runtime_settings.mode.execution_mode != 'paper':
        raise ValueError('paper_only_experiments')
    if cycles < 5 or cycles > 200:
        raise ValueError('cycles_out_of_bounds')

    run_id = f"exp_{uuid.uuid4().hex[:10]}"
    settings_before = copy.deepcopy(api_models.runtime_settings)

    baseline_reset = reset_paper_state(db)
    baseline = _run_window(db, cycles, 'baseline')

    reset_paper_state(db)
    old_value = _get_nested(api_models.runtime_settings, change_path)
    _set_nested(api_models.runtime_settings, change_path, change_value)
    variant = _run_window(db, cycles, 'variant')

    _set_nested(api_models.runtime_settings, change_path, old_value)

    control = None
    if include_control_rerun:
        reset_paper_state(db)
        control = _run_window(db, cycles, 'control_rerun')

    result = {
        'run_id': run_id,
        'name': name,
        'methodology': {
            'paper_only': True,
            'one_change_at_a_time': True,
            'sequential_windows_in_live_market_time': True,
            'workflow': ['baseline', 'variant'] + (['control_rerun'] if include_control_rerun else []),
            'interpretation_warning': 'baseline/variant are sequential windows in changing market conditions; treat small deltas as inconclusive',
        },
        'spec': {
            'paper_only': True,
            'one_change': {'path': change_path, 'old': old_value, 'new': change_value},
            'cycles': cycles,
            'include_control_rerun': include_control_rerun,
            'baseline_starting_equity_usd': settings.paper_starting_equity_usd,
        },
        'settings_snapshot_before': settings_before.model_dump(),
        'baseline_reset': baseline_reset,
        'baseline_metrics': baseline,
        'variant_metrics': variant,
        'control_rerun_metrics': control,
        'classification': _classify(baseline, variant, control),
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
