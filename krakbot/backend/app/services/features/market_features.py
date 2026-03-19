import random


def compute_market_features(market: dict) -> dict:
    trend = random.choice(["up", "down", "flat"])
    return {
        "returns": {
            "ret_1m": random.uniform(-0.01, 0.01),
            "ret_5m": random.uniform(-0.02, 0.02),
            "ret_15m": random.uniform(-0.03, 0.03),
            "ret_1h": random.uniform(-0.05, 0.05),
            "ret_4h": random.uniform(-0.1, 0.1),
            "momentum_score": random.uniform(-1, 1),
            "acceleration_score": random.uniform(-1, 1),
        },
        "volatility": {
            "rv_5m": random.uniform(0, 1),
            "rv_15m": random.uniform(0, 1),
            "rv_1h": random.uniform(0, 1),
            "volatility_state": random.choice(["low", "normal", "high"]),
        },
        "trend": {
            "trend_5m": trend,
            "trend_15m": trend,
            "trend_1h": trend,
            "trend_4h": trend,
            "trend_alignment_score": random.uniform(0, 1),
            "trend_quality_score": random.uniform(0, 1),
        },
        "volume": {
            "volume_zscore_5m": random.uniform(-3, 3),
            "volume_zscore_1h": random.uniform(-3, 3),
            "volume_acceleration": random.uniform(-1, 1),
        },
        "orderbook": {
            "imbalance_10bp": random.uniform(-1, 1),
            "imbalance_25bp": random.uniform(-1, 1),
            "micro_pressure_score": random.uniform(0, 1),
            "book_depth_score": random.uniform(0, 1),
            "slippage_estimate_bps": random.uniform(1, 20),
        },
        "derivatives": {
            "oi_change_5m": random.uniform(-0.2, 0.2),
            "oi_change_15m": random.uniform(-0.3, 0.3),
            "oi_change_1h": random.uniform(-0.5, 0.5),
            "funding_state": random.choice(["positive", "neutral", "negative"]),
        },
        "structure": {
            "distance_from_1h_high": random.uniform(0, 0.05),
            "distance_from_1h_low": random.uniform(0, 0.05),
            "distance_from_4h_high": random.uniform(0, 0.1),
            "distance_from_4h_low": random.uniform(0, 0.1),
            "breakout_state": random.choice(["none", "attempt", "confirmed"]),
        },
        "quality": {
            "liquidity_score": random.uniform(0, 1),
            "freshness_score": random.uniform(0, 1),
            "data_completeness_score": random.uniform(0.8, 1),
            "source_health_score": random.uniform(0.8, 1),
        },
    }
