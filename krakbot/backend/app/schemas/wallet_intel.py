from pydantic import BaseModel, Field


class WalletPipelineRunRequest(BaseModel):
    provider: str = Field(default="manual")
    dry_run: bool = False


class WalletToggleExclusionRequest(BaseModel):
    wallet_id: str
    force_exclude: bool
