from pydantic import BaseModel
from datetime import datetime


class AutonomyEvent(BaseModel):
    event_id: int
    ts: datetime
    run_id: str | None = None
    entity_type: str
    entity_id: str
    event_type: str
    severity: str
    payload: dict
