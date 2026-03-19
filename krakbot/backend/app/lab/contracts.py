from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ExecutionMode(str, Enum):
    PAPER = "paper"
    LIVE_HYPERLIQUID = "live_hyperliquid"


class TradeSide(str, Enum):
    LONG = "long"
    SHORT = "short"
    NO_TRADE = "no_trade"


class MarketSnapshot(BaseModel):
    symbol: str
    mid_price: float
    spread_bps: float
    funding_rate_8h: float = 0.0
    mark_price: float
    volume_1m_usd: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AccountSnapshot(BaseModel):
    equity_usd: float
    free_collateral_usd: float
    open_positions: int
    daily_pnl_pct: float


class DeterministicFeatures(BaseModel):
    r_1m: float
    r_5m: float
    zscore_20: float
    momentum_5: float
    spread_bps: float
    volume_1m_usd: float


class MetaScores(BaseModel):
    trend_score: float = Field(ge=-1.0, le=1.0)
    mean_reversion_score: float = Field(ge=-1.0, le=1.0)
    liquidity_score: float = Field(ge=0.0, le=1.0)


class EvidenceRef(BaseModel):
    key: str
    value: float | str


class FeaturePacket(BaseModel):
    packet_version: str = "fp.v1"
    packet_id: str
    symbol: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    market: MarketSnapshot
    account: AccountSnapshot
    features: DeterministicFeatures
    scores: MetaScores
    risk_profile_id: str
    model_profile_id: str


class DecisionOutput(BaseModel):
    schema_version: str = "decision.v1"
    side: TradeSide
    confidence: float = Field(ge=0.0, le=1.0)
    thesis: str
    risks: list[str] = Field(default_factory=list)
    invalidation: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    requested_notional_usd: float = Field(ge=0.0)


class GateResult(BaseModel):
    allowed: bool
    reasons: list[str] = Field(default_factory=list)
    max_allowed_notional_usd: float = 0.0


class ExecutionRequest(BaseModel):
    mode: ExecutionMode
    symbol: str
    side: Literal["buy", "sell"]
    notional_usd: float
    reduce_only: bool = False


class ExecutionResult(BaseModel):
    accepted: bool
    broker_order_id: str | None = None
    fill_price: float | None = None
    filled_notional_usd: float | None = None
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CycleLog(BaseModel):
    cycle_id: str
    packet: FeaturePacket
    decision: DecisionOutput
    gate: GateResult
    execution: ExecutionResult | None
    labels: dict[str, Any] = Field(default_factory=dict)


class ModeState(BaseModel):
    execution_mode: ExecutionMode = ExecutionMode.PAPER
    live_armed: bool = False
    risk_profile_id: str = "risk.paper.v1"
    model_profile_id: str = "model.qwen35-9b.local.v1"
    score_profile_id: str = "score.default.v1"
