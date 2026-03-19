from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.db_models import ConfigProfileDB

router = APIRouter(tags=["profiles"])


class ProfileUpsert(BaseModel):
    profile_id: str
    profile_type: str
    version: str
    active: bool = False
    payload: dict


@router.get('/profiles')
def list_profiles(profile_type: str | None = None, db: Session = Depends(get_db)):
    q = db.query(ConfigProfileDB)
    if profile_type:
        q = q.filter(ConfigProfileDB.profile_type == profile_type)
    rows = q.order_by(ConfigProfileDB.profile_type, ConfigProfileDB.version.desc()).all()
    return {"items": [
        {
            "profile_id": r.profile_id,
            "profile_type": r.profile_type,
            "version": r.version,
            "active": r.active,
            "payload": r.payload,
        }
        for r in rows
    ]}


@router.post('/profiles')
def upsert_profile(req: ProfileUpsert, db: Session = Depends(get_db)):
    row = db.get(ConfigProfileDB, req.profile_id)
    if not row:
        row = ConfigProfileDB(
            profile_id=req.profile_id,
            profile_type=req.profile_type,
            version=req.version,
            active=req.active,
            payload=req.payload,
        )
        db.add(row)
    else:
        row.profile_type = req.profile_type
        row.version = req.version
        row.active = req.active
        row.payload = req.payload

    if req.active:
        db.query(ConfigProfileDB).filter(
            ConfigProfileDB.profile_type == req.profile_type,
            ConfigProfileDB.profile_id != req.profile_id,
        ).update({"active": False})

    db.commit()
    return {"ok": True}


@router.post('/profiles/{profile_id}/activate')
def activate_profile(profile_id: str, db: Session = Depends(get_db)):
    row = db.get(ConfigProfileDB, profile_id)
    if not row:
        raise HTTPException(status_code=404, detail="profile_not_found")
    db.query(ConfigProfileDB).filter(ConfigProfileDB.profile_type == row.profile_type).update({"active": False})
    row.active = True
    db.commit()
    return {"ok": True, "profile_id": profile_id, "profile_type": row.profile_type}
