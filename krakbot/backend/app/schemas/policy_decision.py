from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class PositionSizing(BaseModel):
    notional_usd: float | None
    max_leverage: float | None
    entry_style: str | None


class GateChecks(BaseModel):
    schema_valid: bool
    freshness_ok: bool
    liquidity_ok: bool
    volatility_ok: bool
    contradiction_ok: bool
    crowdedness_ok: bool
    extension_ok: bool
    cooldown_ok: bool
    max_positions_ok: bool
    max_total_notional_ok: bool
    daily_loss_ok: bool
    direction_allowed: bool


class RiskProfileSnapshot(BaseModel):
    profile_name: str
    max_open_positions: int
    max_notional_per_trade: float
    max_total_notional: float
    daily_loss_limit_usd: float


class PolicyDecision(BaseModel):
    policy_version: str = "1.0"
    policy_decision_id: str
    packet_id: str
    decision_generated_at: datetime
    evaluated_at: datetime
    coin: str
    symbol: str
    requested_action: Literal["long", "short", "no_trade"]
    final_action: Literal["allow_trade", "downgrade_to_watch", "block_invalid_output", "block_risk", "block_market_conditions", "block_operational", "block_mode_disabled"]
    execution_mode: Literal["paper", "live_hyperliquid"]
    position_sizing: PositionSizing
    gate_checks: GateChecks
    reasons: list[str]
    downgrade_or_block_reason: str | None
    risk_profile: RiskProfileSnapshot
    leverage_bucket_audit: dict | None = None
