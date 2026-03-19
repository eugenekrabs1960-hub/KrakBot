from __future__ import annotations

from app.lab.contracts import DecisionOutput, FeaturePacket, GateResult, TradeSide
from app.lab.profiles import RiskProfile


def run_policy_gate(packet: FeaturePacket, decision: DecisionOutput, risk: RiskProfile) -> GateResult:
    reasons: list[str] = []

    if decision.side == TradeSide.NO_TRADE:
        reasons.append("decision_is_no_trade")
        return GateResult(allowed=False, reasons=reasons, max_allowed_notional_usd=0.0)

    if decision.confidence < risk.min_confidence:
        reasons.append("confidence_below_threshold")

    if packet.features.spread_bps > risk.max_spread_bps:
        reasons.append("spread_too_wide")

    if packet.account.open_positions >= risk.max_positions:
        reasons.append("too_many_open_positions")

    max_allowed = min(risk.max_notional_per_trade_usd, packet.account.free_collateral_usd * 0.2)
    if decision.requested_notional_usd > max_allowed:
        reasons.append("requested_notional_above_limit")

    return GateResult(
        allowed=not reasons,
        reasons=reasons,
        max_allowed_notional_usd=max_allowed,
    )
