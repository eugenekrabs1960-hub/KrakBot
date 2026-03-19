from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from app.models.db_models import LoopRunDB


def start_loop_run(db: Session, loop_type: str) -> str:
    run_id = f"loop_{uuid.uuid4().hex[:12]}"
    db.add(LoopRunDB(
        run_id=run_id,
        loop_type=loop_type,
        status="running",
        started_at=datetime.now(timezone.utc),
        finished_at=None,
        duration_ms=None,
        message=None,
    ))
    db.commit()
    return run_id


def finish_loop_run(db: Session, run_id: str, status: str, started: datetime, message: str | None = None):
    row = db.get(LoopRunDB, run_id)
    if not row:
        return
    finished = datetime.now(timezone.utc)
    row.finished_at = finished
    row.duration_ms = int((finished - started).total_seconds() * 1000)
    row.status = status
    row.message = message
    db.commit()
