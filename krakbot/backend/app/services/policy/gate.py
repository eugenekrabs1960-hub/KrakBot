from datetime import datetime, timezone
import uuid

from app.schemas.policy_decision import PolicyDecision
from app.services.policy.checks import check_market_quality
from app.services.policy.sizing import fixed_small_notional


def _assign_paper_leverage(packet, decision, checks, settings, final_action: str) -> tuple[float, str]:
    # default-safe leverage
    lev = 1.0
    tier = 'default_1x'

    if final_action != 'allow_trade':
        return lev, tier

    # paper-only adaptive leverage; live remains unchanged
    if packet.decision_context.mode != 'paper':
        return 1.0, 'live_mode_fixed_1x'

    # warning/quality downgrades force 1x
    warning = (
        (not checks['freshness_ok']) or
        (not checks['liquidity_ok']) or
        (not checks['volatility_ok']) or
        (packet.ml_scores.contradiction_score > 0.70) or
        (packet.ml_scores.crowdedness_score > 0.70) or
        (packet.ml_scores.extension_score > 0.75) or
        (packet.ml_scores.fragility_score > 0.70)
    )
    if warning:
        return 1.0, 'warning_forced_1x'

    setup = decision.setup_type
    eligible = setup in {'mean_reversion', 'trend_continuation', 'breakout_confirmation'}
    if not eligible:
        return 1.0, 'setup_not_eligible_1x'

    conf = float(decision.confidence)
    tqp = float(packet.ml_scores.trade_quality_prior)
    contradiction = float(packet.ml_scores.contradiction_score)
    crowded = float(packet.ml_scores.crowdedness_score)
    extension = float(packet.ml_scores.extension_score)
    fragility = float(packet.ml_scores.fragility_score)
    freshness = float(packet.features.quality.freshness_score)
    liquidity = float(packet.features.quality.liquidity_score)
    rv1h = float(packet.features.volatility.rv_1h)

    # strongest clean setups => 2x (3x hard-cap path exists but intentionally very restrictive)
    if (
        conf >= 0.78 and tqp >= 0.72 and
        contradiction <= 0.30 and crowded <= 0.35 and extension <= 0.40 and fragility <= 0.35 and
        freshness >= 0.70 and liquidity >= 0.55 and rv1h <= 0.55
    ):
        if float(settings.leverage_cap) >= 3.0 and conf >= 0.90 and tqp >= 0.85 and contradiction <= 0.20 and crowded <= 0.25 and extension <= 0.30 and fragility <= 0.25:
            return 3.0, 'extreme_clean_3x_paper_cap'
        return 2.0, 'strongest_clean_2x'

    # clearly strong clean setups => 1.5x
    if (
        conf >= 0.68 and tqp >= 0.62 and
        contradiction <= 0.45 and crowded <= 0.50 and extension <= 0.55 and fragility <= 0.50 and
        freshness >= 0.50 and liquidity >= 0.35
    ):
        return 1.5, 'strong_clean_1p5x'

    return 1.0, 'default_1x'


def evaluate_policy(packet, decision, mode_settings, risk_profile, settings) -> PolicyDecision:
    checks = check_market_quality(packet, settings, mode_settings.execution_mode)
    schema_valid = True
    direction_allowed = (decision.action != 'long' or settings.allow_long) and (decision.action != 'short' or settings.allow_short)

    current_open = int(packet.policy_context.current_open_positions)
    base_notional = float(fixed_small_notional(settings, risk_profile))

    final_action = 'allow_trade'
    reasons = []
    block_reason = None


    fs = getattr(packet.optional_signals, 'feature_engine_status', None) or {}
    realtime_feature_degraded = bool(fs.get('degraded'))

    if decision.action == 'no_trade':
        final_action = 'downgrade_to_watch'
        reasons.append('model_no_trade')
    elif not mode_settings.trading_enabled or (mode_settings.execution_mode == 'live_hyperliquid' and not mode_settings.live_armed):
        final_action = 'block_mode_disabled'
        block_reason = 'trading disabled or live not armed'
    elif mode_settings.execution_mode == 'paper' and realtime_feature_degraded:
        final_action = 'block_market_conditions'
        block_reason = 'realtime_feature_prerequisites_missing'
        reasons.append('feature_engine_degraded')
    elif not all([checks['freshness_ok'], checks['liquidity_ok'], checks['volatility_ok']]):
        final_action = 'block_market_conditions'
        block_reason = 'market_quality'
        if not checks['freshness_ok']:
            reasons.append('freshness_check_failed')
        if not checks['liquidity_ok']:
            reasons.append('liquidity_check_failed')
        if not checks['volatility_ok']:
            reasons.append('volatility_check_failed')
    elif not all([checks['contradiction_ok'], checks['crowdedness_ok'], checks['extension_ok'], checks['cooldown_ok']]):
        final_action = 'block_risk'
        block_reason = 'risk_environment'
        if not checks['contradiction_ok']:
            reasons.append('contradiction_check_failed')
        if not checks['crowdedness_ok']:
            reasons.append('crowdedness_check_failed')
        if not checks['extension_ok']:
            reasons.append('extension_check_failed')
        if not checks['cooldown_ok']:
            reasons.append('cooldown_check_failed')

    lev, lev_reason = _assign_paper_leverage(packet, decision, checks, settings, final_action)
    lev = min(max(1.0, float(lev)), 3.0) if mode_settings.execution_mode == 'paper' else 1.0
    effective_notional = base_notional * lev if final_action == 'allow_trade' else 0.0

    estimated_total_notional = current_open * base_notional
    max_positions_ok = current_open < risk_profile['max_open_positions']
    max_total_ok = (estimated_total_notional + effective_notional) <= risk_profile['max_total_notional']


    # setup-specific selectivity knob: tighten mean_reversion allow_trade via runtime confidence floor
    mr_floor = float(getattr(settings, 'mean_reversion_min_confidence', 0.0) or 0.0)
    if final_action == 'allow_trade' and decision.setup_type == 'mean_reversion' and float(decision.confidence or 0.0) < mr_floor:
        final_action = 'downgrade_to_watch'
        block_reason = 'mean_reversion_selectivity'
        reasons.append('mean_reversion_confidence_below_floor')
        lev = 1.0
        effective_notional = 0.0

    if final_action == 'allow_trade' and not all([max_positions_ok, max_total_ok, direction_allowed]):
        final_action = 'block_risk'
        block_reason = 'portfolio_limits'
        if not max_positions_ok:
            reasons.append('max_open_positions_failed')
        if not max_total_ok:
            reasons.append('max_total_notional_failed')
        if not direction_allowed:
            reasons.append('direction_not_allowed')
        lev = 1.0
        effective_notional = 0.0

    if final_action == 'allow_trade':
        reasons.append(f'leverage_policy:{lev_reason}')

    notional = effective_notional if final_action == 'allow_trade' else None
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
        position_sizing={'notional_usd': notional, 'max_leverage': lev, 'entry_style': decision.execution_preference.entry_style_hint},
        gate_checks={
            'schema_valid': schema_valid,
            **checks,
            'max_positions_ok': max_positions_ok,
            'max_total_notional_ok': max_total_ok,
            'daily_loss_ok': True,
            'direction_allowed': direction_allowed,
        },
        reasons=reasons,
        downgrade_or_block_reason=block_reason,
        risk_profile={
            'profile_name': risk_profile['name'],
            'max_open_positions': risk_profile['max_open_positions'],
            'max_notional_per_trade': risk_profile['max_notional_per_trade'],
            'max_total_notional': risk_profile['max_total_notional'],
            'daily_loss_limit_usd': risk_profile['daily_loss_limit_usd'],
        },
    )
