from datetime import datetime
from pydantic import BaseModel


class ExecutionRecord(BaseModel):
    execution_id: str
    packet_id: str
    policy_decision_id: str
    mode: str
    symbol: str
    action: str
    notional_usd: float
    status: str
    fill_price: float | None = None
    filled_notional_usd: float | None = None
    broker_order_id: str | None = None
    reason: str | None = None
    created_at: datetime
