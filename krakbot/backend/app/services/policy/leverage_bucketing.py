from __future__ import annotations

from app.core.config import settings


def _parse_buckets(s: str) -> list[int]:
    out: list[int] = []
    for x in str(s or '').split(','):
        x = x.strip()
        if not x:
            continue
        try:
            out.append(int(x))
        except Exception:
            continue
    return sorted(set(out))


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


def _scores(packet, decision) -> tuple[float, float, dict, dict]:
    conf = _clamp(getattr(decision, 'confidence', 0.0) or 0.0)
    invalidation_clarity = 1.0 if getattr(decision, 'invalidation', None) is not None else 0.35
    thesis = str(getattr(decision, 'thesis_summary', '') or '').strip()
    thesis_coherence = 0.75 if len(thesis) >= 24 else 0.55
    conviction_score = _clamp(0.6 * conf + 0.25 * invalidation_clarity + 0.15 * thesis_coherence)

    q = packet.features.quality
    m = packet.ml_scores
    market_quality_score = _clamp(
        0.30 * float(q.freshness_score)
        + 0.30 * float(q.liquidity_score)
        + 0.10 * (1.0 - min(1.0, float(packet.features.volatility.rv_1h) / 0.02))
        + 0.10 * (1.0 - float(m.contradiction_score))
        + 0.08 * (1.0 - float(m.crowdedness_score))
        + 0.07 * (1.0 - float(m.extension_score))
        + 0.05 * (1.0 - float(m.fragility_score))
    )
    conviction_components = {
        'model_confidence': round(float(conf), 4),
        'thesis_coherence': round(float(thesis_coherence), 4),
        'invalidation_clarity': round(float(invalidation_clarity), 4),
    }
    market_quality_components = {
        'freshness_score': round(float(q.freshness_score), 4),
        'liquidity_score': round(float(q.liquidity_score), 4),
        'rv_1h': round(float(packet.features.volatility.rv_1h), 6),
        'contradiction_score': round(float(m.contradiction_score), 4),
        'crowdedness_score': round(float(m.crowdedness_score), 4),
        'extension_score': round(float(m.extension_score), 4),
        'fragility_score': round(float(m.fragility_score), 4),
    }
    return conviction_score, market_quality_score, conviction_components, market_quality_components


def _thresholds() -> dict[int, tuple[float, float]]:
    return {
        3: (float(settings.paper_bucket_3_min_conviction), float(settings.paper_bucket_3_min_market_quality)),
        6: (float(settings.paper_bucket_6_min_conviction), float(settings.paper_bucket_6_min_market_quality)),
        9: (float(settings.paper_bucket_9_min_conviction), float(settings.paper_bucket_9_min_market_quality)),
        18: (float(settings.paper_bucket_18_min_conviction), float(settings.paper_bucket_18_min_market_quality)),
    }


def _candidate_bucket(conviction_score: float, market_quality_score: float, active: list[int]) -> tuple[int, str]:
    thresholds = _thresholds()
    for b in sorted([x for x in active if x in thresholds], reverse=True):
        cmin, qmin = thresholds[b]
        if conviction_score >= cmin and market_quality_score >= qmin:
            return b, f'bucket_{b}_threshold_pass'
    return 3, 'bucket_3_default'


def _caution_flags(packet) -> list[str]:
    m = packet.ml_scores
    flags: list[str] = []
    if float(m.contradiction_score) > float(settings.paper_bucket_9_max_contradiction):
        flags.append('contradiction_high')
    if float(m.crowdedness_score) > float(settings.paper_bucket_9_max_crowdedness):
        flags.append('crowdedness_high')
    if float(m.extension_score) > float(settings.paper_bucket_9_max_extension):
        flags.append('extension_high')
    if float(m.fragility_score) > float(settings.paper_bucket_9_max_fragility):
        flags.append('fragility_high')
    return flags


def enforce_paper_bucket(packet, decision, *, final_action: str, current_leverage: float) -> dict:
    mode = str(getattr(packet.decision_context, 'mode', 'paper') or 'paper')
    active = _parse_buckets(settings.paper_leverage_active_buckets)
    deferred = _parse_buckets(settings.paper_leverage_deferred_buckets)

    conviction_score, market_quality_score, cc, mqc = _scores(packet, decision)
    candidate_bucket, reason = _candidate_bucket(conviction_score, market_quality_score, active)

    caution_flags: list[str] = []
    downgrade_reason_code = 'none'
    cap_clip_reason_code = 'none'

    enforced_bucket: int | None = None
    enforced_leverage: float | None = None
    clipped_leverage: float | None = None

    if final_action == 'allow_trade' and mode == 'paper' and bool(settings.paper_leverage_bucketing_enabled):
        enforced_bucket = int(candidate_bucket)
        enforced_leverage = float(enforced_bucket)

        # deferred bucket lockout (18x non-enforced in chunk-2)
        if enforced_bucket in deferred:
            downgrade_reason_code = f'deferred_bucket_locked:{enforced_bucket}'
            enforced_bucket = 9 if 9 in active else (6 if 6 in active else 3)
            enforced_leverage = float(enforced_bucket)

        # caution downgrade rules
        if enforced_bucket >= 9:
            caution_flags = _caution_flags(packet)
            if caution_flags:
                enforced_bucket = 6 if 6 in active else 3
                enforced_leverage = float(enforced_bucket)
                downgrade_reason_code = f'downgrade_due_to_caution:{"|".join(caution_flags)}'

        # hard cap clip
        cap = float(settings.leverage_cap or 1.0)
        if float(enforced_leverage or 1.0) > cap:
            clipped_leverage = cap
            cap_clip_reason_code = 'hard_leverage_cap'
    else:
        reason = 'not_enforced_non_allow_or_non_paper'

    applied_leverage = float(clipped_leverage if clipped_leverage is not None else (enforced_leverage if enforced_leverage is not None else current_leverage))

    return {
        'bucketing_enabled': bool(settings.paper_leverage_bucketing_enabled),
        'bucket_version': str(settings.paper_leverage_bucket_version),
        'mode_scope': 'paper_only',
        'active_buckets': active,
        'deferred_buckets': deferred,

        'candidate_bucket': int(candidate_bucket),
        'enforced_bucket': enforced_bucket,
        'enforced_leverage': enforced_leverage,
        'clipped_leverage': clipped_leverage,

        'bucket_reason_code': reason,
        'downgrade_reason_code': downgrade_reason_code,
        'cap_clip_reason_code': cap_clip_reason_code,

        'conviction_score': round(float(conviction_score), 4),
        'market_quality_score': round(float(market_quality_score), 4),
        'conviction_components': cc,
        'market_quality_components': mqc,
        'caution_flags': caution_flags,

        'assigned_leverage_current': float(current_leverage),
        'applied_leverage': applied_leverage,
        'enforcement_applied': bool(final_action == 'allow_trade' and mode == 'paper' and bool(settings.paper_leverage_bucketing_enabled)),
    }
