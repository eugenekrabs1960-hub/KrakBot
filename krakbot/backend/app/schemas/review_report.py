from datetime import datetime
from pydantic import BaseModel


class ReviewReport(BaseModel):
    review_version: str = "1.0"
    review_id: str
    generated_at: datetime
    packet_id: str
    decision_id: str
    policy_decision_id: str
    reviewer: str = "supervisor_stub"
    findings: list[str]
    recommendation: str
