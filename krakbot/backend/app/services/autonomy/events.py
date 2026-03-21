from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.db_models import AutonomyEventDB

_REQUIRED_EVENT_FIELDS = ['change_path', 'old_value', 'new_value', 'reason_code', 'target_mode']


def _enforce_payload_fields(payload: dict) -> dict:
    out = dict(payload or {})
    for k in _REQUIRED_EVENT_FIELDS:
        out.setdefault(k, None)
    return out


def emit_event(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    event_type: str,
    severity: str = 'info',
    payload: dict | None = None,
    run_id: str | None = None,
) -> None:
    row = AutonomyEventDB(
        ts=datetime.now(timezone.utc),
        run_id=run_id,
        entity_type=entity_type,
        entity_id=entity_id,
        event_type=event_type,
        severity=severity,
        payload=_enforce_payload_fields(payload or {}),
    )
    db.add(row)
