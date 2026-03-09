from pydantic import BaseModel, Field
from typing import Literal


class StrategySummary(BaseModel):
    strategy_instance_id: str
    name: Literal['trend_following', 'mean_reversion', 'breakout']
    enabled: bool
    market: str
    pnl_usd: float = 0
    drawdown_pct: float = 0
    win_rate_pct: float = 0
    trade_count: int = 0
    status: str = 'idle'


class StrategyInstanceCreate(BaseModel):
    strategy_name: Literal['trend_following', 'mean_reversion', 'breakout']
    market: str = 'SOL/USD'
    instrument_type: str = 'spot'
    starting_equity_usd: float = Field(default=10000, gt=0)
    params: dict = Field(default_factory=dict)
