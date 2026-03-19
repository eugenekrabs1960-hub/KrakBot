from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class OutcomeLabel(BaseModel):
    outcome_version: str = "1.0"
    outcome_id: str
    packet_id: str
    decision_id: str
    policy_decision_id: str
    generated_at: datetime
    coin: str
    symbol: str
    decision_action: Literal["long", "short", "no_trade"]
    policy_result: str
    execution_mode: Literal["paper", "live_hyperliquid"]
    evaluation_horizon: Literal["15m", "1h", "4h"]
    decision_timestamp: datetime
    evaluation_timestamp: datetime
    market_outcome: dict
    trade_outcome: dict
    evaluation: dict
    mistake_tags: list[str]
    summary: str
