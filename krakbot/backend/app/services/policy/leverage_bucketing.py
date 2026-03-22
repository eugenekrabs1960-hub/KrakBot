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


def compute_bucket_audit(packet, decision, policy) -> dict:
    mode = str(getattr(packet.decision_context, 'mode', 'paper') or 'paper')

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

    thresholds = {
        3: (float(settings.paper_bucket_3_min_conviction), float(settings.paper_bucket_3_min_market_quality)),
        6: (float(settings.paper_bucket_6_min_conviction), float(settings.paper_bucket_6_min_market_quality)),
        9: (float(settings.paper_bucket_9_min_conviction), float(settings.paper_bucket_9_min_market_quality)),
        18: (float(settings.paper_bucket_18_min_conviction), float(settings.paper_bucket_18_min_market_quality)),
    }

    active = _parse_buckets(settings.paper_leverage_active_buckets)
    deferred = _parse_buckets(settings.paper_leverage_deferred_buckets)

    candidate_bucket = 3
    reason = 'bucket_3_default'
    for b in sorted([x for x in active if x in thresholds], reverse=True):
        cmin, qmin = thresholds[b]
        if conviction_score >= cmin and market_quality_score >= qmin:
            candidate_bucket = b
            reason = f'bucket_{b}_threshold_pass'
            break

    caution_flags: list[str] = []
    if candidate_bucket >= 9:
        if float(m.contradiction_score) > float(settings.paper_bucket_9_max_contradiction):
            caution_flags.append('contradiction_high')
        if float(m.crowdedness_score) > float(settings.paper_bucket_9_max_crowdedness):
            caution_flags.append('crowdedness_high')
        if float(m.extension_score) > float(settings.paper_bucket_9_max_extension):
            caution_flags.append('extension_high')
        if float(m.fragility_score) > float(settings.paper_bucket_9_max_fragility):
            caution_flags.append('fragility_high')
    if caution_flags and candidate_bucket > 3:
        candidate_bucket = 6 if candidate_bucket >= 9 else 3
        reason = f'downgraded_due_to_caution:{"|".join(caution_flags)}'

    if candidate_bucket in deferred:
        reason = f'deferred_bucket_locked:{candidate_bucket}'
        candidate_bucket = 9 if 9 in active else 6 if 6 in active else 3

    assigned_leverage_current = float((policy.position_sizing.max_leverage or 1.0) if getattr(policy, 'position_sizing', None) else 1.0)

    return {
        'bucketing_enabled': bool(settings.paper_leverage_bucketing_enabled),
        'bucket_version': str(settings.paper_leverage_bucket_version),
        'mode_scope': 'paper_only',
        'active_buckets': active,
        'deferred_buckets': deferred,
        'candidate_bucket': int(candidate_bucket),
        'bucket_reason_code': reason,
        'conviction_score': round(float(conviction_score), 4),
        'market_quality_score': round(float(market_quality_score), 4),
        'conviction_components': {
            'model_confidence': round(float(conf), 4),
            'thesis_coherence': round(float(thesis_coherence), 4),
            'invalidation_clarity': round(float(invalidation_clarity), 4),
        },
        'market_quality_components': {
            'freshness_score': round(float(q.freshness_score), 4),
            'liquidity_score': round(float(q.liquidity_score), 4),
            'rv_1h': round(float(packet.features.volatility.rv_1h), 6),
            'contradiction_score': round(float(m.contradiction_score), 4),
            'crowdedness_score': round(float(m.crowdedness_score), 4),
            'extension_score': round(float(m.extension_score), 4),
            'fragility_score': round(float(m.fragility_score), 4),
        },
        'caution_flags': caution_flags,
        # chunk-1: do not enforce leverage changes yet
        'assigned_leverage_current': assigned_leverage_current,
        'bucket_preview_leverage': float(candidate_bucket),
        'enforcement_applied': False,
    }
