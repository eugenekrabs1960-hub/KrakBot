from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.autonomy_stage1 import _pick_candidate


def detect_weakness_and_propose(db: Session) -> dict:
    # bounded stage1 detector/proposer reuse
    return _pick_candidate(db)
