from pydantic import BaseModel


class LiveMarketEvent(BaseModel):
    type: str
    venue: str
    market: str
    instrument_type: str = "spot"
    ts: int
    payload: dict
