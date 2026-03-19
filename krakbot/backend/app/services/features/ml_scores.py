def compute_ml_scores(features: dict) -> dict:
    m = features["returns"]["momentum_score"]
    liq = features["quality"]["liquidity_score"]
    contradiction = abs(features["returns"]["ret_1m"] - features["returns"]["ret_15m"]) * 10
    attention = max(0.0, min(1.0, 0.4 * liq + 0.6 * abs(m)))
    opportunity = max(0.0, min(1.0, 0.6 * abs(m) + 0.4 * (1 - contradiction)))
    tradability = max(0.0, min(1.0, 0.5 * liq + 0.5 * (1 - features["orderbook"]["slippage_estimate_bps"] / 30)))
    return {
        "attention_score": attention,
        "opportunity_score": opportunity,
        "tradability_score": tradability,
        "market_regime": "trend" if m > 0.2 else "range",
        "regime_compatibility_score": 0.7,
        "move_probability_up_15m": 0.5 + 0.2 * m,
        "move_probability_down_15m": 0.5 - 0.2 * m,
        "move_probability_up_1h": 0.5 + 0.25 * m,
        "move_probability_down_1h": 0.5 - 0.25 * m,
        "trade_quality_prior": tradability,
        "no_trade_prior": 1 - tradability,
        "contradiction_score": contradiction,
        "crowdedness_score": 0.3,
        "extension_score": abs(features["returns"]["ret_1h"]),
        "fragility_score": 1 - features["quality"]["source_health_score"],
    }
