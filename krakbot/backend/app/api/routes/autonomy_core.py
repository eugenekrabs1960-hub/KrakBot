from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.models.db_models import (
    AutonomyPromotionDB,
    AutonomyRollbackDB,
    AutonomyEventDB,
    RuntimeConfigSnapshotDB,
)
from app.services.autonomy.promotion_manager import create_hypothesis_from_recommendation, create_promotion, apply_promotion
from app.services.autonomy.rollback_controller import apply_rollback

router = APIRouter(tags=['autonomy-core'])


@router.post('/autonomy/core/hypotheses/from-recommendation/{recommendation_id}')
def autonomy_core_hypothesis_from_recommendation(recommendation_id: str, db: Session = Depends(get_db)):
    try:
        hyp = create_hypothesis_from_recommendation(db, recommendation_id)
        db.commit()
        return {'hypothesis_id': hyp.hypothesis_id, 'status': hyp.status, 'change_path': hyp.change_path, 'change_value': hyp.change_value}
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/autonomy/core/promotions/create')
def autonomy_core_create_promotion(hypothesis_id: str, reason: str = 'autonomy_candidate', db: Session = Depends(get_db)):
    try:
        pro = create_promotion(db, hypothesis_id=hypothesis_id, reason=reason)
        db.commit()
        return {'promotion_id': pro.promotion_id, 'status': pro.status, 'target_mode': pro.target_mode, 'pre_snapshot_id': pro.pre_snapshot_id}
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/autonomy/core/promotions/{promotion_id}/apply')
def autonomy_core_apply_promotion(promotion_id: str, db: Session = Depends(get_db)):
    try:
        pro = apply_promotion(db, promotion_id)
        db.commit()
        return {
            'promotion_id': pro.promotion_id,
            'status': pro.status,
            'target_mode': pro.target_mode,
            'pre_snapshot_id': pro.pre_snapshot_id,
            'post_snapshot_id': pro.post_snapshot_id,
            'payload': pro.payload,
        }
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/autonomy/core/promotions')
def autonomy_core_promotions(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(AutonomyPromotionDB).order_by(desc(AutonomyPromotionDB.created_at)).limit(max(1, min(limit, 200))).all()
    return {'items': [
        {
            'promotion_id': r.promotion_id,
            'created_at': r.created_at,
            'status': r.status,
            'hypothesis_id': r.hypothesis_id,
            'target_mode': r.target_mode,
            'target_scope': r.target_scope,
            'pre_snapshot_id': r.pre_snapshot_id,
            'post_snapshot_id': r.post_snapshot_id,
            'reason': r.reason,
            'payload': r.payload,
        }
        for r in rows
    ]}


@router.get('/autonomy/core/promotions/{promotion_id}')
def autonomy_core_promotion_detail(promotion_id: str, db: Session = Depends(get_db)):
    r = db.get(AutonomyPromotionDB, promotion_id)
    if not r:
        raise HTTPException(status_code=404, detail='not_found')
    return {
        'promotion_id': r.promotion_id,
        'created_at': r.created_at,
        'status': r.status,
        'hypothesis_id': r.hypothesis_id,
        'target_mode': r.target_mode,
        'target_scope': r.target_scope,
        'pre_snapshot_id': r.pre_snapshot_id,
        'post_snapshot_id': r.post_snapshot_id,
        'reason': r.reason,
        'payload': r.payload,
    }


@router.post('/autonomy/core/rollbacks/{promotion_id}/apply')
def autonomy_core_apply_rollback(promotion_id: str, trigger_reason: str = 'manual', db: Session = Depends(get_db)):
    try:
        rb = apply_rollback(db, promotion_id, trigger_reason=trigger_reason)
        db.commit()
        return {
            'rollback_id': rb.rollback_id,
            'status': rb.status,
            'promotion_id': rb.promotion_id,
            'from_snapshot_id': rb.from_snapshot_id,
            'to_snapshot_id': rb.to_snapshot_id,
            'trigger_reason': rb.trigger_reason,
        }
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/autonomy/core/rollbacks')
def autonomy_core_rollbacks(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(AutonomyRollbackDB).order_by(desc(AutonomyRollbackDB.created_at)).limit(max(1, min(limit, 200))).all()
    return {'items': [
        {
            'rollback_id': r.rollback_id,
            'created_at': r.created_at,
            'status': r.status,
            'promotion_id': r.promotion_id,
            'from_snapshot_id': r.from_snapshot_id,
            'to_snapshot_id': r.to_snapshot_id,
            'trigger_reason': r.trigger_reason,
            'payload': r.payload,
        }
        for r in rows
    ]}


@router.get('/autonomy/core/events')
def autonomy_core_events(limit: int = 200, db: Session = Depends(get_db)):
    rows = db.query(AutonomyEventDB).order_by(desc(AutonomyEventDB.ts), desc(AutonomyEventDB.event_id)).limit(max(1, min(limit, 1000))).all()
    return {'items': [
        {
            'event_id': r.event_id,
            'ts': r.ts,
            'run_id': r.run_id,
            'entity_type': r.entity_type,
            'entity_id': r.entity_id,
            'event_type': r.event_type,
            'severity': r.severity,
            'payload': r.payload,
        }
        for r in rows
    ]}


@router.get('/autonomy/core/snapshots/{snapshot_id}')
def autonomy_core_snapshot(snapshot_id: str, db: Session = Depends(get_db)):
    r = db.get(RuntimeConfigSnapshotDB, snapshot_id)
    if not r:
        raise HTTPException(status_code=404, detail='not_found')
    return {
        'snapshot_id': r.snapshot_id,
        'created_at': r.created_at,
        'source': r.source,
        'mode': r.mode,
        'hash': r.hash,
        'settings': r.settings_json,
    }
