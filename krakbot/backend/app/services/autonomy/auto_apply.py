from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import asc

from app.core.config import settings
from app.models.db_models import AutonomyPromotionDB
from app.services.autonomy.events import emit_event
from app.services.autonomy.promotion_manager import apply_promotion


def _age_seconds(created_at) -> float:
    if created_at is None:
        return 10**9
    now = datetime.now(timezone.utc)
    try:
        ts = created_at.astimezone(timezone.utc)
    except Exception:
        ts = created_at
    return max(0.0, (now - ts).total_seconds())


def auto_apply_tick(db: Session) -> dict:
    rows = (
        db.query(AutonomyPromotionDB)
        .filter(AutonomyPromotionDB.status == 'pending')
        .order_by(asc(AutonomyPromotionDB.created_at))
        .limit(max(1, int(settings.autonomy_auto_apply_max_per_tick or 1)))
        .all()
    )
    if not rows:
        return {'ok': True, 'status': 'idle', 'applied': 0, 'blocked': 0, 'reason': 'no_pending_promotions'}

    applied = 0
    blocked = 0
    details = []
    max_age = int(settings.autonomy_promotion_max_age_sec or 1800)

    for r in rows:
        age = _age_seconds(r.created_at)
        if age > max_age:
            r.status = 'blocked'
            payload = dict(r.payload or {})
            change_path = payload.get('change_path')
            new_value = payload.get('new_value')
            emit_event(db, entity_type='promotion', entity_id=r.promotion_id, event_type='blocked', severity='warn', payload={
                'change_path': change_path,
                'old_value': None,
                'new_value': new_value,
                'reason_code': 'promotion_too_old_for_auto_apply',
                'target_mode': r.target_mode,
                'age_sec': round(age, 3),
                'max_age_sec': max_age,
            })
            blocked += 1
            details.append({'promotion_id': r.promotion_id, 'status': 'blocked', 'reason_code': 'promotion_too_old_for_auto_apply', 'age_sec': age})
            continue

        before = r.status
        out = apply_promotion(db, r.promotion_id)
        after = out.status
        if after == 'applied':
            applied += 1
        elif after == 'blocked':
            blocked += 1
        details.append({'promotion_id': r.promotion_id, 'before': before, 'after': after, 'target_mode': r.target_mode})

    return {'ok': True, 'status': 'ok', 'applied': applied, 'blocked': blocked, 'items': details}
