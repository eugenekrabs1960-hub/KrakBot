from pydantic import BaseModel


class TradeRow(BaseModel):
    strategy_instance_id: str
    side: str
    qty: float
    entry_price: float
    exit_price: float | None = None
    realized_pnl_usd: float | None = None
    ts: str
