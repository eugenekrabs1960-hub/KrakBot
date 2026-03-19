from __future__ import annotations

from statistics import mean, pstdev

from app.lab.contracts import DeterministicFeatures
from app.lab.state import STATE


def compute_features(spread_bps: float, volume_1m_usd: float) -> DeterministicFeatures:
    prices = STATE.price_history
    p_now = prices[-1]
    p_1m = prices[-2] if len(prices) > 1 else p_now
    p_5m = prices[-6] if len(prices) > 5 else prices[0]
    window = prices[-20:] if len(prices) >= 20 else prices
    mu = mean(window)
    sigma = pstdev(window) or 1e-9
    zscore = (p_now - mu) / sigma

    r_1m = (p_now / p_1m) - 1 if p_1m else 0.0
    r_5m = (p_now / p_5m) - 1 if p_5m else 0.0

    return DeterministicFeatures(
        r_1m=r_1m,
        r_5m=r_5m,
        zscore_20=zscore,
        momentum_5=r_5m,
        spread_bps=spread_bps,
        volume_1m_usd=volume_1m_usd,
    )
