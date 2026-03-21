from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from app.api import models as api_models
from app.models.db_models import RuntimeConfigSnapshotDB
from app.schemas.settings import SettingsBundle


def _hash_settings(settings_json: dict) -> str:
    b = json.dumps(settings_json, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(b).hexdigest()


def create_snapshot(db: Session, *, source: str, mode: str, settings_json: dict) -> RuntimeConfigSnapshotDB:
    row = RuntimeConfigSnapshotDB(
        snapshot_id=f"snap_{uuid.uuid4().hex[:12]}",
        created_at=datetime.now(timezone.utc),
        source=source,
        mode=mode,
        settings_json=settings_json,
        hash=_hash_settings(settings_json),
    )
    db.add(row)
    db.flush()
    return row


def create_runtime_snapshot(db: Session, *, source: str = 'manual') -> RuntimeConfigSnapshotDB:
    settings_json = api_models.runtime_settings.model_dump()
    mode = str((settings_json.get('mode') or {}).get('execution_mode') or 'paper')
    return create_snapshot(db, source=source, mode=mode, settings_json=settings_json)


def get_snapshot(db: Session, snapshot_id: str) -> RuntimeConfigSnapshotDB | None:
    return db.get(RuntimeConfigSnapshotDB, snapshot_id)


def apply_snapshot(db: Session, snapshot_id: str) -> RuntimeConfigSnapshotDB:
    row = db.get(RuntimeConfigSnapshotDB, snapshot_id)
    if not row:
        raise ValueError('snapshot_not_found')
    bundle = SettingsBundle.model_validate(row.settings_json)
    api_models.runtime_settings.mode = bundle.mode
    api_models.runtime_settings.universe = bundle.universe
    api_models.runtime_settings.loop = bundle.loop
    api_models.runtime_settings.model = bundle.model
    api_models.runtime_settings.risk = bundle.risk
    return row
