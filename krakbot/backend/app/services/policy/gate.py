from datetime import datetime, timezone
import uuid

from app.schemas.policy_decision import PolicyDecision
from app.services.policy.checks import check_market_quality
from app.services.policy.sizing import fixed_small_notional


def evaluate_policy(packet, decision, mode_settings, risk_profile, settings) -> PolicyDecision:
    checks = check_market_quality(packet, settings, mode_settings.execution_mode)
    schema_valid = True
    direction_allowed = (decision.action != "long" or settings.allow_long) and (decision.action != "short" or settings.allow_short)

    # portfolio checks
    current_open = int(packet.policy_context.current_open_positions)
    per_trade = float(fixed_small_notional(settings, risk_profile))
    estimated_total_notional = current_open * per_trade

    max_positions_ok = current_open < risk_profile["max_open_positions"]
    max_total_ok = estimated_total_notional + per_trade <= risk_profile["max_total_notional"]

    final_action = "allow_trade"
    reasons = []
    block_reason = None

    if decision.action == "no_trade":
        final_action = "downgrade_to_watch"
        reasons.append("model_no_trade")
    elif not mode_settings.trading_enabled or (mode_settings.execution_mode == "live_hyperliquid" and not mode_settings.live_armed):
        final_action = "block_mode_disabled"
        block_reason = "trading disabled or live not armed"
    elif not all([checks["freshness_ok"], checks["liquidity_ok"], checks["volatility_ok"]]):
        final_action = "block_market_conditions"
        block_reason = "market_quality"
        if not checks["freshness_ok"]:
            reasons.append("freshness_check_failed")
        if not checks["liquidity_ok"]:
            reasons.append("liquidity_check_failed")
        if not checks["volatility_ok"]:
            reasons.append("volatility_check_failed")
    elif not all([checks["contradiction_ok"], checks["crowdedness_ok"], checks["extension_ok"], checks["cooldown_ok"]]):
        final_action = "block_risk"
        block_reason = "risk_environment"
        if not checks["contradiction_ok"]:
            reasons.append("contradiction_check_failed")
        if not checks["crowdedness_ok"]:
            reasons.append("crowdedness_check_failed")
        if not checks["extension_ok"]:
            reasons.append("extension_check_failed")
        if not checks["cooldown_ok"]:
            reasons.append("cooldown_check_failed")
    elif not all([max_positions_ok, max_total_ok, direction_allowed]):
        final_action = "block_risk"
        block_reason = "portfolio_limits"
        if not max_positions_ok:
            reasons.append("max_open_positions_failed")
        if not max_total_ok:
            reasons.append("max_total_notional_failed")
        if not direction_allowed:
            reasons.append("direction_not_allowed")

    notional = per_trade if final_action == "allow_trade" else None
    return PolicyDecision(
        policy_decision_id=f"pol_{uuid.uuid4().hex[:12]}",
        packet_id=packet.packet_id,
        decision_generated_at=decision.generated_at,
        evaluated_at=datetime.now(timezone.utc),
        coin=packet.coin,
        symbol=packet.symbol,
        requested_action=decision.action,
        final_action=final_action,
        execution_mode=mode_settings.execution_mode,
        position_sizing={"notional_usd": notional, "max_leverage": settings.leverage_cap, "entry_style": decision.execution_preference.entry_style_hint},
        gate_checks={
            "schema_valid": schema_valid,
            **checks,
            "max_positions_ok": max_positions_ok,
            "max_total_notional_ok": max_total_ok,
            "daily_loss_ok": True,
            "direction_allowed": direction_allowed,
        },
        reasons=reasons,
        downgrade_or_block_reason=block_reason,
        risk_profile={
            "profile_name": risk_profile["name"],
            "max_open_positions": risk_profile["max_open_positions"],
            "max_notional_per_trade": risk_profile["max_notional_per_trade"],
            "max_total_notional": risk_profile["max_total_notional"],
            "daily_loss_limit_usd": risk_profile["daily_loss_limit_usd"],
        },
    )
