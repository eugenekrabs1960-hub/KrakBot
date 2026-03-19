from fastapi import APIRouter
from app.api.models import runtime_settings
from app.schemas.settings import SettingsBundle

router = APIRouter(tags=["settings"])


@router.get('/settings')
def get_settings():
    return runtime_settings.model_dump()


@router.post('/settings')
def update_settings(bundle: SettingsBundle):
    global runtime_settings
    runtime_settings = bundle
    return {"ok": True, "settings": runtime_settings.model_dump()}
