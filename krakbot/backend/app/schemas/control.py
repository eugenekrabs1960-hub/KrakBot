from pydantic import BaseModel
from typing import Literal


class BotCommand(BaseModel):
    command: Literal['start', 'stop', 'pause', 'resume', 'reload']


class StrategyToggle(BaseModel):
    strategy_instance_id: str
    enabled: bool


class ExecutionVenueUpdate(BaseModel):
    default_venue: Literal['paper', 'hyperliquid']


class LiveTradingEnableRequest(BaseModel):
    confirm_phrase: str
    max_notional_usd_per_order: float = 250.0
    max_daily_loss_usd: float = 100.0
    allowed_agents: list[str] = ['jason']


class LiveTradingDisableRequest(BaseModel):
    confirm_phrase: str
