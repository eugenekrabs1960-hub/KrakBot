from app.schemas.decision_output import DecisionOutput


def validate_output(decision: DecisionOutput) -> tuple[bool, str | None]:
    try:
        DecisionOutput.model_validate(decision.model_dump())
        return True, None
    except Exception as e:
        return False, str(e)
