from pydantic import BaseModel
from typing import Literal


class StrategySummary(BaseModel):
    strategy_instance_id: str
    name: Literal["trend_following", "mean_reversion", "breakout"]
    enabled: bool
    market: str
    pnl_usd: float
    drawdown_pct: float
    win_rate_pct: float
    trade_count: int
