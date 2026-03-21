from __future__ import annotations

import copy
import time
from datetime import datetime, timezone
import uuid
from collections import Counter

import requests
from sqlalchemy.orm import Session

from app.api import models as api_models
from app.core.config import settings
from app.models.db_models import ExperimentRunDB, ExecutionRecordDB
from app.services.decision_engine import run_decision_cycle
from app.services.paper_account import compute_paper_account_from_exec
from app.services.paper_reset import reset_paper_state


SAFE_EXPERIMENT_KNOBS = {
    # strict paper-safe stage1 whitelist
    'risk.mean_reversion_min_confidence': {'type': 'float', 'min': 0.60, 'max': 0.75},
    'universe.max_candidates_per_cycle': {'type': 'int', 'min': 1, 'max': 2},
    'model.temperature': {'type': 'float', 'min': 0.10, 'max': 0.25},
    'risk.max_notional_per_trade': {'type': 'float', 'min': 40.0, 'max': 60.0},
}


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


def _model_online() -> bool:
    try:
        headers = {}
        if settings.local_model_api_key:
            headers['Authorization'] = f"Bearer {settings.local_model_api_key}"
        r = requests.get(f"{settings.local_model_base_url.rstrip('/')}/v1/models", headers=headers, timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _normalize_whitelisted_value(path: str, value):
    cfg = SAFE_EXPERIMENT_KNOBS.get(path)
    if not cfg:
        raise ValueError('change_path_not_whitelisted')

    lo, hi = cfg['min'], cfg['max']
    if cfg['type'] == 'int':
        try:
            v = int(round(float(value)))
        except Exception as exc:
            raise ValueError('change_value_invalid') from exc
        if v < int(lo) or v > int(hi):
            raise ValueError('change_value_out_of_bounds')
        return v

    try:
        v = float(value)
    except Exception as exc:
        raise ValueError('change_value_invalid') from exc
    if v < float(lo) or v > float(hi):
        raise ValueError('change_value_out_of_bounds')
    return round(v, 4)


def _run_window(db: Session, cycles: int, label: str, cycle_delay_sec: float) -> dict:
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
    aborted = False
    abort_reason = None

    for _ in range(cycles):
        if settings.experiment_abort_on_model_offline and not _model_online():
            aborted = True
            abort_reason = 'model_offline'
            break

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

        time.sleep(max(0.05, float(cycle_delay_sec)))

    ended_at = datetime.now(timezone.utc)

    exec_rows = [r.payload for r in db.query(ExecutionRecordDB).filter(ExecutionRecordDB.mode == 'paper').all()]
    acct = compute_paper_account_from_exec(exec_rows)

    return {
        'label': label,
        'cycles': cycles,
        'aborted': aborted,
        'abort_reason': abort_reason,
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
    if base.get('aborted') or var.get('aborted') or (control and control.get('aborted')):
        return 'inconclusive'
    b = _total_equity(base)
    v = _total_equity(var)
    c = _total_equity(control) if control else b
    if (v - max(b, c)) > 5:
        return 'keep'
    if (v - min(b, c)) < -5:
        return 'reject'
    return 'inconclusive'


def run_experiment(db: Session, *, name: str, change_path: str, change_value, cycles: int = 20, include_control_rerun: bool = False) -> dict:
    if api_models.runtime_settings.mode.execution_mode != 'paper':
        raise ValueError('paper_only_experiments')
    if cycles < 5 or cycles > 200:
        raise ValueError('cycles_out_of_bounds')

    # stage1 safety gate: whitelist + hard bounds only
    bounded_change_value = _normalize_whitelisted_value(change_path, change_value)

    run_id = f"exp_{uuid.uuid4().hex[:10]}"
    settings_before = copy.deepcopy(api_models.runtime_settings)

    # dedicated low-pressure experiment mode (restored after run)
    prev_candidate_cap = api_models.runtime_settings.universe.max_candidates_per_cycle
    prev_llm_safe = settings.llm_safe_mode
    prev_llm_cap = settings.llm_safe_mode_max_candidates
    prev_repair_disabled = settings.llm_disable_repair
    prev_concurrency = settings.llm_max_concurrent_requests

    api_models.runtime_settings.universe.max_candidates_per_cycle = 1
    settings.llm_safe_mode = True
    settings.llm_safe_mode_max_candidates = 1
    settings.llm_disable_repair = True
    settings.llm_max_concurrent_requests = 1

    cycle_delay = float(settings.experiment_cycle_delay_sec)

    try:
        baseline_reset = reset_paper_state(db)
        baseline = _run_window(db, cycles, 'baseline', cycle_delay)

        reset_paper_state(db)
        old_value = _get_nested(api_models.runtime_settings, change_path)
        _set_nested(api_models.runtime_settings, change_path, bounded_change_value)
        variant = _run_window(db, cycles, 'variant', cycle_delay)

        _set_nested(api_models.runtime_settings, change_path, old_value)

        control = None
        if include_control_rerun:
            reset_paper_state(db)
            control = _run_window(db, cycles, 'control_rerun', cycle_delay)

        result = {
            'run_id': run_id,
            'name': name,
            'methodology': {
                'paper_only': True,
                'research_mode': True,
                'one_change_at_a_time': True,
                'sequential_windows_in_live_market_time': True,
                'workflow': ['baseline', 'variant'] + (['control_rerun'] if include_control_rerun else []),
                'interpretation_warning': 'baseline/variant are sequential windows in changing market conditions; treat small deltas as inconclusive',
                'safe_whitelist_applied': True,
                'safe_whitelist': SAFE_EXPERIMENT_KNOBS,
                'low_pressure_guardrails': {
                    'cycles_default': 20,
                    'include_control_rerun_default': False,
                    'candidate_cap': 1,
                    'repair_disabled': True,
                    'llm_concurrency': 1,
                    'cycle_delay_sec': cycle_delay,
                    'abort_on_model_offline': bool(settings.experiment_abort_on_model_offline),
                },
            },
            'spec': {
                'paper_only': True,
                'one_change': {'path': change_path, 'old': old_value, 'new': bounded_change_value},
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
    finally:
        api_models.runtime_settings.universe.max_candidates_per_cycle = prev_candidate_cap
        settings.llm_safe_mode = prev_llm_safe
        settings.llm_safe_mode_max_candidates = prev_llm_cap
        settings.llm_disable_repair = prev_repair_disabled
        settings.llm_max_concurrent_requests = prev_concurrency
