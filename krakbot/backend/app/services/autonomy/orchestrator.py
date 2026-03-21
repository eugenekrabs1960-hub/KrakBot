from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.db_models import AutonomyRunDB, AutonomyRecommendationDB, AutonomyPromotionDB
from app.services.autonomy.detector import detect_weakness_and_propose
from app.services.experiments import run_experiment
from app.services.autonomy.evaluator import summarize_experiment
from app.services.autonomy.events import emit_event
from app.services.autonomy.promotion_manager import create_hypothesis_from_recommendation, create_promotion


def _active_run_exists(db: Session) -> bool:
    r = db.query(AutonomyRunDB).filter(AutonomyRunDB.status == 'running').order_by(desc(AutonomyRunDB.started_at)).first()
    return r is not None


def _pending_promotion_exists(db: Session) -> bool:
    r = db.query(AutonomyPromotionDB).filter(AutonomyPromotionDB.status == 'pending').order_by(desc(AutonomyPromotionDB.created_at)).first()
    return r is not None


def run_once(db: Session, *, trigger: str = 'manual', cycles: int = 8) -> dict:
    if _active_run_exists(db):
        return {'ok': False, 'status': 'skipped', 'reason': 'active_run_exists'}
    if _pending_promotion_exists(db):
        return {'ok': False, 'status': 'skipped', 'reason': 'pending_promotion_exists'}

    run = AutonomyRunDB(
        run_id=f"arun_{uuid.uuid4().hex[:12]}",
        started_at=datetime.now(timezone.utc),
        finished_at=None,
        status='running',
        phase='detect',
        trigger=trigger,
        payload={},
    )
    db.add(run)
    db.flush()

    try:
        candidate = detect_weakness_and_propose(db)
        run.phase = 'propose'
        emit_event(db, entity_type='run', entity_id=run.run_id, event_type='proposed', run_id=run.run_id, payload={
            'change_path': candidate.get('change_path'),
            'old_value': None,
            'new_value': candidate.get('change_value'),
            'reason_code': 'candidate_proposed',
            'target_mode': 'paper',
        })

        run.phase = 'experiment'
        exp = run_experiment(
            db,
            name=f"auto-orch-{candidate['change_path'].replace('.', '-')}-{candidate['change_value']}",
            change_path=candidate['change_path'],
            change_value=candidate['change_value'],
            cycles=max(5, min(20, int(cycles))),
            include_control_rerun=False,
        )

        run.phase = 'evaluate'
        summary = summarize_experiment(exp)

        recommendation = {
            'recommendation_id': f"rec_{uuid.uuid4().hex[:10]}",
            'created_at': datetime.now(timezone.utc).isoformat(),
            'source': 'autonomy_orchestrator_chunk2',
            'scope': 'paper_only_research_mode',
            'status': summary['classification'],
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
                'baseline_total_equity_usd': summary['equity']['baseline'],
                'variant_total_equity_usd': summary['equity']['variant'],
                'baseline_fees_usd': summary['fees_usd']['baseline'],
                'variant_fees_usd': summary['fees_usd']['variant'],
                'fills_baseline': summary['fills']['baseline'],
                'fills_variant': summary['fills']['variant'],
                'equity_delta': summary['equity']['delta'],
                'major_reason': summary['major_reason'],
            },
            'summary_text': f"{candidate['weak_spot']}: {candidate['change_path']} -> {candidate['change_value']} ({summary['classification']})",
        }

        rec_row = AutonomyRecommendationDB(
            recommendation_id=recommendation['recommendation_id'],
            created_at=datetime.now(timezone.utc),
            status=recommendation['status'],
            payload=recommendation,
        )
        db.add(rec_row)
        db.flush()

        promotion_candidate = None
        if summary['classification'] == 'keep':
            run.phase = 'promote'
            hyp = create_hypothesis_from_recommendation(db, recommendation['recommendation_id'])
            pro = create_promotion(db, hypothesis_id=hyp.hypothesis_id, reason='orchestrator_keep_candidate')
            old_value = None
            try:
                # infer from runtime snapshot payload of pre snapshot
                pre = pro.pre_snapshot_id
                # leave None if not directly available here
            except Exception:
                pass

            promo_summary = {
                'weak_spot_detected': candidate['weak_spot'],
                'hypothesis_text': candidate['rationale'],
                'change_path': candidate['change_path'],
                'old_value': old_value,
                'new_value': candidate['change_value'],
                'experiment_classification': summary['classification'],
                'key_evidence_summary': {
                    'fills': summary['fills'],
                    'fees_usd': summary['fees_usd'],
                    'equity_delta': summary['equity']['delta'],
                    'major_reason': summary['major_reason'],
                },
            }
            pro.payload = {**(pro.payload or {}), 'promotion_candidate_summary': promo_summary}
            emit_event(db, entity_type='promotion', entity_id=pro.promotion_id, event_type='candidate_created', payload={
                'change_path': candidate['change_path'],
                'old_value': old_value,
                'new_value': candidate['change_value'],
                'reason_code': 'keep_candidate_created',
                'target_mode': pro.target_mode,
            }, run_id=run.run_id)
            promotion_candidate = {
                'hypothesis_id': hyp.hypothesis_id,
                'promotion_id': pro.promotion_id,
                'status': pro.status,
                'summary': promo_summary,
            }

        run.status = 'completed'
        run.finished_at = datetime.now(timezone.utc)
        run.payload = {
            'candidate': candidate,
            'experiment_run_id': exp.get('run_id'),
            'classification': summary['classification'],
            'promotion_candidate': promotion_candidate,
        }
        emit_event(db, entity_type='run', entity_id=run.run_id, event_type='completed', payload={
            'change_path': candidate.get('change_path'),
            'old_value': None,
            'new_value': candidate.get('change_value'),
            'reason_code': f"run_completed_{summary['classification']}",
            'target_mode': 'paper',
        }, run_id=run.run_id)
        return {'ok': True, 'run_id': run.run_id, 'classification': summary['classification'], 'promotion_candidate': promotion_candidate}
    except Exception as e:
        run.status = 'failed'
        run.finished_at = datetime.now(timezone.utc)
        run.payload = {'error': str(e)}
        emit_event(db, entity_type='run', entity_id=run.run_id, event_type='failed', severity='error', payload={
            'change_path': None,
            'old_value': None,
            'new_value': None,
            'reason_code': f"run_failed:{type(e).__name__}",
            'target_mode': 'paper',
        }, run_id=run.run_id)
        raise
