from pydantic import BaseModel
from typing import Literal


class BotCommand(BaseModel):
    command: Literal["start", "stop", "pause", "resume", "reload"]


class StrategyToggle(BaseModel):
    strategy_instance_id: str
    enabled: bool
