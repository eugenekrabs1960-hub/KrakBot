from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Reason(BaseModel):
    label: str
    strength: float = Field(ge=0, le=1)
    explanation: str


class Risk(BaseModel):
    label: str
    severity: float = Field(ge=0, le=1)
    explanation: str


class Invalidation(BaseModel):
    type: Literal["price_level", "regime_break", "volatility_break", "thesis_failure", "null"]
    value: float | None = None
    reason: str | None = None


class Targets(BaseModel):
    take_profit_hint: float | None = None
    expected_move_magnitude: Literal["small", "medium", "large", "null"] = "null"


class Alternative(BaseModel):
    action: Literal["long", "short", "no_trade"]
    reason: str


class ExecutionPreference(BaseModel):
    urgency: Literal["low", "normal", "high"]
    entry_style_hint: Literal["market", "limit", "market_or_aggressive_limit", "passive_limit", "none"]


class DecisionOutput(BaseModel):
    decision_version: str = "1.0"
    packet_id: str
    generated_at: datetime
    model_name: str
    model_role: str = "local_analyst"
    coin: str
    symbol: str
    action: Literal["long", "short", "no_trade"]
    setup_type: Literal["trend_continuation", "breakout_confirmation", "mean_reversion", "range_rejection", "unclear"]
    horizon: Literal["15m", "1h", "4h"]
    confidence: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    thesis_summary: str
    reasons: list[Reason]
    risks: list[Risk]
    invalidation: Invalidation | None = None
    targets: Targets
    evidence_used: list[str]
    evidence_ignored: list[str] = []
    alternatives_considered: list[Alternative]
    execution_preference: ExecutionPreference

    @model_validator(mode="after")
    def validate_contract(self):
        if len(self.reasons) < 2:
            raise ValueError("at least 2 reasons required")
        if len(self.risks) < 1:
            raise ValueError("at least 1 risk required")
        if self.action in {"long", "short"} and self.invalidation is None:
            raise ValueError("invalidation required for trade actions")
        return self
