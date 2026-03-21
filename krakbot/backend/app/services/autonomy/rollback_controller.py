from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from app.models.db_models import AutonomyRollbackDB, AutonomyPromotionDB, AutonomyHypothesisDB
from app.services.autonomy.events import emit_event
from app.services.autonomy.snapshots import apply_snapshot, create_runtime_snapshot


def apply_rollback(db: Session, promotion_id: str, *, trigger_reason: str = 'manual') -> AutonomyRollbackDB:
    pro = db.get(AutonomyPromotionDB, promotion_id)
    if not pro:
        raise ValueError('promotion_not_found')
    if not pro.pre_snapshot_id:
        raise ValueError('promotion_missing_pre_snapshot')

    hyp = db.get(AutonomyHypothesisDB, pro.hypothesis_id)
    change_path = (pro.payload or {}).get('change_path') or (hyp.change_path if hyp else None)
    new_value = (pro.payload or {}).get('new_value') or (hyp.change_value if hyp else None)

    apply_snapshot(db, pro.pre_snapshot_id)
    after = create_runtime_snapshot(db, source='autonomy_rollback_post')

    rb = AutonomyRollbackDB(
        rollback_id=f"rb_{uuid.uuid4().hex[:12]}",
        created_at=datetime.now(timezone.utc),
        status='applied',
        promotion_id=promotion_id,
        from_snapshot_id=pro.post_snapshot_id or '',
        to_snapshot_id=pro.pre_snapshot_id,
        trigger_reason=trigger_reason,
        payload={'after_snapshot_id': after.snapshot_id},
    )
    db.add(rb)

    pro.status = 'reverted'
    if hyp:
        hyp.status = 'rolled_back'

    emit_event(db, entity_type='rollback', entity_id=rb.rollback_id, event_type='applied', payload={
        'change_path': change_path,
        'old_value': new_value,
        'new_value': 'reverted_to_pre_snapshot',
        'reason_code': trigger_reason,
        'target_mode': pro.target_mode,
    })
    return rb
