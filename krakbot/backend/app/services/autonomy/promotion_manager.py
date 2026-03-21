from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api import models as api_models
from app.models.db_models import (
    AutonomyHypothesisDB,
    AutonomyPromotionDB,
    AutonomyRecommendationDB,
)
from app.services.autonomy.events import emit_event
from app.services.autonomy.snapshots import create_runtime_snapshot


def _get_nested(obj, path: str):
    cur = obj
    for p in path.split('.'):
        cur = getattr(cur, p)
    return cur


def _set_nested(obj, path: str, value):
    parts = path.split('.')
    cur = obj
    for p in parts[:-1]:
        cur = getattr(cur, p)
    setattr(cur, parts[-1], value)


def resolve_target(main_mode: str) -> dict:
    if main_mode == 'paper':
        return {'target_mode': 'paper', 'target_scope': 'main_runtime', 'live_apply_supported': False}
    if main_mode == 'live_hyperliquid':
        return {'target_mode': 'live_hyperliquid', 'target_scope': 'main_runtime', 'live_apply_supported': False}
    return {'target_mode': main_mode or 'paper', 'target_scope': 'main_runtime', 'live_apply_supported': False}


def ensure_one_change_at_a_time(db: Session) -> bool:
    active = (
        db.query(AutonomyPromotionDB)
        .filter(AutonomyPromotionDB.status == 'applied')
        .order_by(desc(AutonomyPromotionDB.created_at))
        .first()
    )
    return active is None


def create_hypothesis_from_recommendation(db: Session, recommendation_id: str) -> AutonomyHypothesisDB:
    row = db.get(AutonomyRecommendationDB, recommendation_id)
    if not row:
        raise ValueError('recommendation_not_found')
    p = row.payload or {}
    rec = p.get('recommendation') or {}
    hyp = AutonomyHypothesisDB(
        hypothesis_id=f"hyp_{uuid.uuid4().hex[:12]}",
        created_at=datetime.now(timezone.utc),
        status='proposed',
        weak_spot=str(rec.get('weak_spot') or 'unknown'),
        rationale=str(rec.get('rationale') or 'autonomy_recommendation'),
        change_path=str(rec.get('change_path') or ''),
        change_value=str(rec.get('change_value')),
        source_run_id=None,
        payload=p,
    )
    db.add(hyp)
    emit_event(db, entity_type='hypothesis', entity_id=hyp.hypothesis_id, event_type='created', payload={
        'change_path': hyp.change_path,
        'old_value': None,
        'new_value': hyp.change_value,
        'reason_code': 'from_recommendation',
        'target_mode': str((api_models.runtime_settings.mode.execution_mode or 'paper')),
    })
    db.flush()
    return hyp


def create_promotion(db: Session, *, hypothesis_id: str, reason: str) -> AutonomyPromotionDB:
    hyp = db.get(AutonomyHypothesisDB, hypothesis_id)
    if not hyp:
        raise ValueError('hypothesis_not_found')
    target = resolve_target(api_models.runtime_settings.mode.execution_mode)
    pre = create_runtime_snapshot(db, source='autonomy_promotion_pre')
    row = AutonomyPromotionDB(
        promotion_id=f"pro_{uuid.uuid4().hex[:12]}",
        created_at=datetime.now(timezone.utc),
        status='pending',
        hypothesis_id=hypothesis_id,
        target_mode=target['target_mode'],
        target_scope=target['target_scope'],
        pre_snapshot_id=pre.snapshot_id,
        post_snapshot_id=None,
        reason=reason,
        payload={'change_path': hyp.change_path, 'new_value': hyp.change_value},
    )
    db.add(row)
    emit_event(db, entity_type='promotion', entity_id=row.promotion_id, event_type='created', payload={
        'change_path': hyp.change_path,
        'old_value': None,
        'new_value': hyp.change_value,
        'reason_code': 'promotion_created',
        'target_mode': row.target_mode,
    })
    db.flush()
    return row


def apply_promotion(db: Session, promotion_id: str) -> AutonomyPromotionDB:
    row = db.get(AutonomyPromotionDB, promotion_id)
    if not row:
        raise ValueError('promotion_not_found')
    hyp = db.get(AutonomyHypothesisDB, row.hypothesis_id)
    if not hyp:
        raise ValueError('hypothesis_not_found')

    if not ensure_one_change_at_a_time(db):
        row.status = 'blocked'
        emit_event(db, entity_type='promotion', entity_id=row.promotion_id, event_type='blocked', severity='warn', payload={
            'change_path': hyp.change_path,
            'old_value': None,
            'new_value': hyp.change_value,
            'reason_code': 'one_change_lock_active',
            'target_mode': row.target_mode,
        })
        return row

    if row.target_mode != 'paper':
        row.status = 'blocked'
        emit_event(db, entity_type='promotion', entity_id=row.promotion_id, event_type='blocked', severity='warn', payload={
            'change_path': hyp.change_path,
            'old_value': None,
            'new_value': hyp.change_value,
            'reason_code': 'live_apply_not_enabled_in_chunk1',
            'target_mode': row.target_mode,
        })
        return row

    old_value = _get_nested(api_models.runtime_settings, hyp.change_path)

    # typed conversion from current leaf type
    new_value = hyp.change_value
    try:
        if isinstance(old_value, bool):
            new_value = str(new_value).lower() in {'1', 'true', 'yes', 'on'}
        elif isinstance(old_value, int) and not isinstance(old_value, bool):
            new_value = int(round(float(new_value)))
        elif isinstance(old_value, float):
            new_value = float(new_value)
    except Exception:
        row.status = 'blocked'
        emit_event(db, entity_type='promotion', entity_id=row.promotion_id, event_type='blocked', severity='warn', payload={
            'change_path': hyp.change_path,
            'old_value': old_value,
            'new_value': hyp.change_value,
            'reason_code': 'change_value_cast_failed',
            'target_mode': row.target_mode,
        })
        return row

    _set_nested(api_models.runtime_settings, hyp.change_path, new_value)
    post = create_runtime_snapshot(db, source='autonomy_promotion_post')

    row.status = 'applied'
    row.post_snapshot_id = post.snapshot_id
    row.payload = {**(row.payload or {}), 'change_path': hyp.change_path, 'old_value': old_value, 'new_value': new_value}
    hyp.status = 'promoted'

    emit_event(db, entity_type='promotion', entity_id=row.promotion_id, event_type='applied', payload={
        'change_path': hyp.change_path,
        'old_value': old_value,
        'new_value': new_value,
        'reason_code': 'applied_paper_target',
        'target_mode': row.target_mode,
    })
    return row
