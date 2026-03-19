from app.schemas.decision_output import DecisionOutput


def repair_output(decision: dict, packet_id: str) -> DecisionOutput:
    decision.setdefault("packet_id", packet_id)
    decision.setdefault("evidence_ignored", [])
    decision.setdefault("alternatives_considered", [{"action": "no_trade", "reason": "repair fallback"}])
    return DecisionOutput.model_validate(decision)
