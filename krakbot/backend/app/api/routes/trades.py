from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.models import runtime_settings
from app.core.database import get_db
from app.services.journal.queries import recent_exec

router = APIRouter(tags=['trades'])


@router.get('/trades')
def trades(limit: int = 100, db: Session = Depends(get_db)):
    n = max(1, min(limit, 500))
    return {'items': recent_exec(db, n), 'mode': runtime_settings.mode.execution_mode}
