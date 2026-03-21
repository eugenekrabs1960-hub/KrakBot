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

    # heuristic bounded choice
    if mr_share > 0.70:
        cur = float(api_models.runtime_settings.risk.mean_reversion_min_confidence)
        proposed = _clamp('risk.mean_reversion_min_confidence', cur + 0.02)
        return {
            'reason': f'mean_reversion_dominance_detected share={mr_share:.2f}',
            'change_path': 'risk.mean_reversion_min_confidence',
            'change_value': proposed,
        }

    if allow > block:
        cur = int(api_models.runtime_settings.universe.max_candidates_per_cycle)
        proposed = _clamp('universe.max_candidates_per_cycle', max(1, cur))
        return {
            'reason': 'keep conservative candidate breadth',
            'change_path': 'universe.max_candidates_per_cycle',
            'change_value': proposed,
        }

    cur = float(api_models.runtime_settings.model.temperature)
    proposed = _clamp('model.temperature', cur - 0.02)
    return {
        'reason': 'reduce decision noise under weak throughput',
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
