from __future__ import annotations

from app.lab.contracts import DeterministicFeatures, MetaScores


def clamp(v: float, low: float, high: float) -> float:
    return max(low, min(high, v))


def compute_scores(features: DeterministicFeatures, target_volume_1m_usd: float) -> MetaScores:
    trend = clamp(features.momentum_5 * 80.0, -1.0, 1.0)
    mean_reversion = clamp(-features.zscore_20 / 3.0, -1.0, 1.0)
    liquidity = clamp(features.volume_1m_usd / target_volume_1m_usd, 0.0, 1.0)
    return MetaScores(
        trend_score=trend,
        mean_reversion_score=mean_reversion,
        liquidity_score=liquidity,
    )
