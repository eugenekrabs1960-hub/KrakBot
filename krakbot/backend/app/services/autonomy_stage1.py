from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import uuid

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api import models as api_models
from app.models.db_models import PolicyDecisionDB, DecisionOutputDB, AutonomyRecommendationDB, ExecutionRecordDB
from app.services.experiments import run_experiment, SAFE_EXPERIMENT_KNOBS


SAFE_BOUNDS = {
    path: (cfg['min'], cfg['max'])
    for path, cfg in SAFE_EXPERIMENT_KNOBS.items()
}


def _clamp(path: str, value):
    lo, hi = SAFE_BOUNDS[path]
    if isinstance(lo, int):
        return int(max(lo, min(hi, int(round(float(value))))))
    return round(float(max(lo, min(hi, float(value)))), 4)


def _safe_ratio(num: float, den: float) -> float:
    return float(num) / float(den) if den else 0.0


def _pick_candidate(db: Session) -> dict:
    # weak-spot detection from recent paper telemetry only
    decisions = db.query(DecisionOutputDB).order_by(desc(DecisionOutputDB.generated_at)).limit(160).all()
    policies = db.query(PolicyDecisionDB).order_by(desc(PolicyDecisionDB.evaluated_at)).limit(160).all()
    executions = (
        db.query(ExecutionRecordDB)
        .filter(ExecutionRecordDB.mode == 'paper')
        .order_by(desc(ExecutionRecordDB.created_at))
        .limit(220)
        .all()
    )

    setup_counts = Counter([(d.payload or {}).get('setup_type', 'unknown') for d in decisions])
    conf_buckets = {'low': [], 'mid': [], 'high': []}
    for d in decisions:
        conf = float((d.payload or {}).get('confidence') or d.confidence or 0.0)
        action = str((d.payload or {}).get('action') or d.action or 'hold')
        if conf < 0.45:
            conf_buckets['low'].append(action)
        elif conf < 0.75:
            conf_buckets['mid'].append(action)
        else:
            conf_buckets['high'].append(action)

    outcomes = Counter([(p.payload or {}).get('final_action', 'unknown') for p in policies])
    allow = outcomes.get('allow_trade', 0)
    block = sum(v for k, v in outcomes.items() if str(k).startswith('block_'))
    watch = outcomes.get('downgrade_to_watch', 0)

    filled = [r for r in executions if (r.payload or {}).get('status') == 'filled' or r.status == 'filled']
    filled_count = len(filled)
    total_fees = sum(float((r.payload or {}).get('fee_usd') or 0.0) for r in filled)
    total_notional = sum(float((r.payload or {}).get('filled_notional_usd') or r.filled_notional_usd or 0.0) for r in filled)
    fee_drag_bps = (total_fees / total_notional * 10_000) if total_notional > 0 else 0.0

    mr_share = _safe_ratio(setup_counts.get('mean_reversion', 0), sum(setup_counts.values()))
    wildcard_share = _safe_ratio(setup_counts.get('wildcard', 0), sum(setup_counts.values()))
    hold_ratio = _safe_ratio(
        sum(1 for d in decisions if str((d.payload or {}).get('action') or d.action or 'hold') == 'hold'),
        len(decisions),
    )

    high_non_hold = _safe_ratio(sum(1 for a in conf_buckets['high'] if a != 'hold'), len(conf_buckets['high']))
    low_non_hold = _safe_ratio(sum(1 for a in conf_buckets['low'] if a != 'hold'), len(conf_buckets['low']))

    evidence = {
        'source': 'recent_paper_telemetry',
        'lookback': {
            'decisions': int(len(decisions)),
            'policies': int(sum(outcomes.values())),
            'paper_executions': int(len(executions)),
            'paper_fills': int(filled_count),
        },
        'signals': {
            'hold_ratio': round(hold_ratio, 4),
            'mean_reversion_share': round(mr_share, 4),
            'wildcard_share': round(wildcard_share, 4),
            'policy_counts': {'allow': int(allow), 'watch': int(watch), 'block': int(block)},
            'fee_drag_bps': round(fee_drag_bps, 2),
            'confidence_non_hold_rate': {
                'low': round(low_non_hold, 4),
                'high': round(high_non_hold, 4),
            },
        },
    }

    # bounded one-change proposal from whitelist only
    if hold_ratio > 0.78 and allow < max(6, block):
        cur = float(api_models.runtime_settings.model.temperature)
        proposed = _clamp('model.temperature', cur + 0.02)
        return {
            'weak_spot': 'over_conservative_no_trade_bias',
            'rationale': f'Hold ratio is high ({hold_ratio:.0%}) with low allow throughput.',
            'telemetry_evidence': evidence,
            'change_path': 'model.temperature',
            'change_value': proposed,
        }

    if fee_drag_bps > 16.0 and filled_count >= 8:
        cur = float(api_models.runtime_settings.risk.max_notional_per_trade)
        proposed = _clamp('risk.max_notional_per_trade', cur - 5)
        return {
            'weak_spot': 'fee_drag_after_costs',
            'rationale': f'Fee drag is elevated ({fee_drag_bps:.1f} bps) across recent paper fills.',
            'telemetry_evidence': evidence,
            'change_path': 'risk.max_notional_per_trade',
            'change_value': proposed,
        }

    if wildcard_share > 0.35 and block > allow:
        cur = int(api_models.runtime_settings.universe.max_candidates_per_cycle)
        proposed = _clamp('universe.max_candidates_per_cycle', cur - 1)
        return {
            'weak_spot': 'weak_wildcard_usefulness_proxy',
            'rationale': 'Wildcard-heavy flow is not converting to allowed trades.',
            'telemetry_evidence': evidence,
            'change_path': 'universe.max_candidates_per_cycle',
            'change_value': proposed,
        }

    if high_non_hold <= low_non_hold + 0.05:
        cur = float(api_models.runtime_settings.risk.mean_reversion_min_confidence)
        proposed = _clamp('risk.mean_reversion_min_confidence', cur + 0.02)
        return {
            'weak_spot': 'confidence_not_separating_actions',
            'rationale': 'High-confidence decisions are not clearly more selective than low-confidence ones.',
            'telemetry_evidence': evidence,
            'change_path': 'risk.mean_reversion_min_confidence',
            'change_value': proposed,
        }

    cur = float(api_models.runtime_settings.risk.mean_reversion_min_confidence)
    proposed = _clamp('risk.mean_reversion_min_confidence', cur + 0.01)
    return {
        'weak_spot': 'baseline_precision_tuning',
        'rationale': 'Default bounded precision tuning pass based on recent paper telemetry.',
        'telemetry_evidence': evidence,
        'change_path': 'risk.mean_reversion_min_confidence',
        'change_value': proposed,
    }


def run_once(db: Session, cycles: int = 8) -> dict:
    candidate = _pick_candidate(db)
    exp_name = f"auto-stage1-{candidate['change_path'].replace('.', '-')}-{candidate['change_value']}"
    exp = run_experiment(
        db,
        name=exp_name,
        change_path=candidate['change_path'],
        change_value=candidate['change_value'],
        cycles=max(5, min(20, int(cycles))),
        include_control_rerun=False,
    )

    recommendation = {
        'recommendation_id': f"rec_{uuid.uuid4().hex[:10]}",
        'created_at': datetime.now(timezone.utc).isoformat(),
        'source': 'autonomy_stage1',
        'scope': 'paper_only_research_mode',
        'status': exp.get('classification', 'inconclusive'),
        'recommendation': {
            'change_path': candidate['change_path'],
            'change_value': candidate['change_value'],
            'rationale': candidate['rationale'],
            'weak_spot': candidate['weak_spot'],
            'bounded_by_whitelist': True,
        },
        'evidence_summary': candidate['telemetry_evidence'],
        'experiment': {
            'run_id': exp.get('run_id'),
            'classification': exp.get('classification'),
            'workflow': (exp.get('methodology') or {}).get('workflow', ['baseline', 'variant']),
            'baseline_total_equity_usd': (exp.get('baseline_metrics', {}).get('paper_account', {}) or {}).get('total_equity_usd'),
            'variant_total_equity_usd': (exp.get('variant_metrics', {}).get('paper_account', {}) or {}).get('total_equity_usd'),
            'baseline_fees_usd': (exp.get('baseline_metrics', {}) or {}).get('fees_usd'),
            'variant_fees_usd': (exp.get('variant_metrics', {}) or {}).get('fees_usd'),
        },
        'summary_text': f"{candidate['weak_spot']}: {candidate['change_path']} -> {candidate['change_value']} ({exp.get('classification', 'inconclusive')})",
    }

    db.add(AutonomyRecommendationDB(
        recommendation_id=recommendation['recommendation_id'],
        created_at=datetime.now(timezone.utc),
        status=recommendation['status'],
        payload=recommendation,
    ))
    db.commit()
    return recommendation
