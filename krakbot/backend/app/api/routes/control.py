from fastapi import APIRouter

from app.schemas.control import BotCommand

router = APIRouter(prefix="/control", tags=["control"])


@router.post("/bot")
def bot_command(payload: BotCommand):
    # TODO: wire into orchestrator state machine
    return {"accepted": True, "command": payload.command}
