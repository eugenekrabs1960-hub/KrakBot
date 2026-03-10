from pydantic import BaseModel, Field


class WalletPipelineRunRequest(BaseModel):
    provider: str = Field(default="manual")
    dry_run: bool = False


class WalletToggleExclusionRequest(BaseModel):
    wallet_id: str
    force_exclude: bool


class WalletToggleInclusionRequest(BaseModel):
    wallet_id: str
    force_include: bool


class WalletAlignmentRequest(BaseModel):
    strategy_instance_id: str | None = None
    trade_ref: str | None = None
    strategy_side: str = Field(default="buy")
    scope: str = Field(default="trade")
