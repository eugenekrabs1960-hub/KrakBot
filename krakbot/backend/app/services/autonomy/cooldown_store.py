from __future__ import annotations

from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.db_models import AutonomyCooldownDB


def set_cooldown(db: Session, *, change_path: str, reason: str) -> AutonomyCooldownDB:
    until = datetime.now(timezone.utc) + timedelta(seconds=int(settings.autonomy_rollback_cooldown_sec or 1800))
    row = db.get(AutonomyCooldownDB, change_path)
    if not row:
        row = AutonomyCooldownDB(change_path=change_path, cooldown_until=until, reason=reason, updated_at=datetime.now(timezone.utc))
        db.add(row)
    else:
        row.cooldown_until = until
        row.reason = reason
        row.updated_at = datetime.now(timezone.utc)
    return row


def is_in_cooldown(db: Session, *, change_path: str) -> bool:
    row = db.get(AutonomyCooldownDB, change_path)
    if not row:
        return False
    now = datetime.now(timezone.utc)
    try:
        ts = row.cooldown_until.astimezone(timezone.utc)
    except Exception:
        ts = row.cooldown_until
    return ts > now
