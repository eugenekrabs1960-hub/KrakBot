from datetime import datetime, timezone
import uuid

from app.schemas.review_report import ReviewReport


def generate_review_stub(packet_id: str, decision_id: str, policy_decision_id: str) -> ReviewReport:
    return ReviewReport(
        review_id=f"rev_{uuid.uuid4().hex[:12]}",
        generated_at=datetime.now(timezone.utc),
        packet_id=packet_id,
        decision_id=decision_id,
        policy_decision_id=policy_decision_id,
        findings=["supervisor loop not enabled; stub report generated"],
        recommendation="keep_in_observation",
    )
