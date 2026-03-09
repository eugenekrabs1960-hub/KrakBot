from pydantic import BaseModel


class MarketSnapshot(BaseModel):
    venue: str
    market: str
    instrument_type: str
    last_price: float
    ts: str
