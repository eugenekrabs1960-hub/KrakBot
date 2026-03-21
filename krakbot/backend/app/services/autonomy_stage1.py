from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import uuid

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api import models as api_models
from app.models.db_models import PolicyDecisionDB, DecisionOutputDB, AutonomyRecommendationDB
from app.services.experiments import run_experiment

SAFE_BOUNDS = {
    'risk.mean_reversion_min_confidence': (0.60, 0.75),
    'universe.max_candidates_per_cycle': (1, 2),
    'model.temperature': (0.10, 0.25),
    'risk.max_notional_per_trade': (40, 60),
}


def _clamp(path: str, value):
    lo, hi = SAFE_BOUNDS[path]
    if isinstance(lo, int):
        return int(max(lo, min(hi, int(value))))
    return float(max(lo, min(hi, float(value))))


def _pick_candidate(db: Session) -> dict:
    # weak-spot detection from recent telemetry
    dec = db.query(DecisionOutputDB).order_by(desc(DecisionOutputDB.generated_at)).limit(120).all()
    pol = db.query(PolicyDecisionDB).order_by(desc(PolicyDecisionDB.evaluated_at)).limit(120).all()

    setups = Counter([(d.payload or {}).get('setup_type', 'unknown') for d in dec])
    mr_share = (setups.get('mean_reversion', 0) / max(1, sum(setups.values())))

    outcomes = Counter([(p.payload or {}).get('final_action', 'unknown') for p in pol])
    allow = outcomes.get('allow_trade', 0)
    block = sum(v for k, v in outcomes.items() if str(k).startswith('block_'))
    watch = outcomes.get('downgrade_to_watch', 0)

    evidence = {
        'recent_decisions': int(sum(setups.values())),
        'mean_reversion_share': round(float(mr_share), 4),
        'policy_counts': {'allow': int(allow), 'watch': int(watch), 'block': int(block)},
    }

    # heuristic bounded choice
    if mr_share > 0.70:
        cur = float(api_models.runtime_settings.risk.mean_reversion_min_confidence)
        proposed = _clamp('risk.mean_reversion_min_confidence', cur + 0.02)
        return {
            'weak_spot': 'mean_reversion_dominance',
            'explanation': f"Mean-reversion dominates recent decisions ({mr_share:.0%}), suggesting selectivity tightening.",
            'telemetry_evidence': evidence,
            'change_path': 'risk.mean_reversion_min_confidence',
            'change_value': proposed,
        }

    if allow > block:
        cur = int(api_models.runtime_settings.universe.max_candidates_per_cycle)
        proposed = _clamp('universe.max_candidates_per_cycle', max(1, cur))
        return {
            'weak_spot': 'throughput_vs_risk_balance',
            'explanation': 'Allow rate exceeds block rate; keep candidate breadth conservative.',
            'telemetry_evidence': evidence,
            'change_path': 'universe.max_candidates_per_cycle',
            'change_value': proposed,
        }

    cur = float(api_models.runtime_settings.model.temperature)
    proposed = _clamp('model.temperature', cur - 0.02)
    return {
        'weak_spot': 'decision_noise_under_low_allow',
        'explanation': 'Low net throughput/edge signal; reduce model temperature to lower action noise.',
        'telemetry_evidence': evidence,
        'change_path': 'model.temperature',
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
        'status': exp.get('classification', 'inconclusive'),
        'candidate': candidate,
        'summary_text': f"{candidate['weak_spot']}: {candidate['change_path']} -> {candidate['change_value']}",
        'experiment': {
            'run_id': exp.get('run_id'),
            'classification': exp.get('classification'),
            'baseline_total_equity_usd': (exp.get('baseline_metrics', {}).get('paper_account', {}) or {}).get('total_equity_usd'),
            'variant_total_equity_usd': (exp.get('variant_metrics', {}).get('paper_account', {}) or {}).get('total_equity_usd'),
        },
    }

    db.add(AutonomyRecommendationDB(
        recommendation_id=recommendation['recommendation_id'],
        created_at=datetime.now(timezone.utc),
        status=recommendation['status'],
        payload=recommendation,
    ))
    db.commit()
    return recommendation
