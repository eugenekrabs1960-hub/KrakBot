def check_market_quality(packet, settings):
    return {
        "freshness_ok": packet.features.quality.freshness_score >= 0.4,
        "liquidity_ok": packet.features.quality.liquidity_score >= settings.min_liquidity_score,
        "volatility_ok": packet.features.volatility.rv_1h <= 0.9,
        "contradiction_ok": packet.ml_scores.contradiction_score <= settings.max_contradiction,
        "crowdedness_ok": packet.ml_scores.crowdedness_score <= settings.max_crowdedness,
        "extension_ok": packet.ml_scores.extension_score <= settings.max_extension,
        "cooldown_ok": not packet.policy_context.cooldown_active,
    }
