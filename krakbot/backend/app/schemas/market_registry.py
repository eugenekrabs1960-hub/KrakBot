from pydantic import BaseModel, Field


class MarketRegistryCreate(BaseModel):
    venue: str = 'kraken'
    symbol: str
    base_asset: str
    quote_asset: str = 'USD'
    instrument_type: str = 'spot'
    enabled: bool = False
    metadata: dict = Field(default_factory=dict)


class MarketToggle(BaseModel):
    enabled: bool
