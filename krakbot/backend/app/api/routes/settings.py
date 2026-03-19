from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import models as api_models
from app.schemas.settings import SettingsBundle
from app.core.database import get_db
from app.models.db_models import ConfigProfileDB, TrackedUniverseDB

router = APIRouter(tags=["settings"])


@router.get('/settings')
def get_settings():
    return api_models.runtime_settings.model_dump()


@router.post('/settings')
def update_settings(bundle: SettingsBundle, db: Session = Depends(get_db)):
    # mutate in-place so existing module references remain consistent
    api_models.runtime_settings.mode = bundle.mode
    api_models.runtime_settings.universe = bundle.universe
    api_models.runtime_settings.loop = bundle.loop
    api_models.runtime_settings.model = bundle.model
    api_models.runtime_settings.risk = bundle.risk

    profile_rows = [
        ("mode", "mode.v1", bundle.mode.model_dump()),
        ("universe", "universe.v1", bundle.universe.model_dump()),
        ("loop", "loop.v1", bundle.loop.model_dump()),
        ("model", "model.v1", bundle.model.model_dump()),
        ("risk", "risk.v1", bundle.risk.model_dump()),
    ]
    for ptype, version, payload in profile_rows:
        pid = f"active:{ptype}:{version}"
        row = db.get(ConfigProfileDB, pid)
        if not row:
            row = ConfigProfileDB(profile_id=pid, profile_type=ptype, version=version, active=True, payload=payload)
            db.add(row)
        else:
            row.payload = payload
            row.active = True
        db.query(ConfigProfileDB).filter(ConfigProfileDB.profile_type == ptype, ConfigProfileDB.profile_id != pid).update({"active": False})

    incoming = {c: True for c in bundle.universe.tracked_coins}
    existing = {r.coin: r for r in db.query(TrackedUniverseDB).all()}
    for coin, enabled in incoming.items():
        if coin in existing:
            existing[coin].enabled = enabled
        else:
            db.add(TrackedUniverseDB(coin=coin, enabled=enabled))
    for coin, row in existing.items():
        if coin not in incoming:
            row.enabled = False

    db.commit()
    return {"ok": True, "settings": api_models.runtime_settings.model_dump()}
