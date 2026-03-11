from pydantic import BaseModel


class TradeRow(BaseModel):
    strategy_instance_id: str
    side: str
    qty: float
    entry_price: float
    exit_price: float | None = None
    realized_pnl_usd: float | None = None
    ts: str


class PaperOrderRequest(BaseModel):
    strategy_instance_id: str
    market: str = 'SOL/USD'
    side: str
    qty: float
    order_type: str = 'market'
    limit_price: float | None = None
    venue: str | None = None
