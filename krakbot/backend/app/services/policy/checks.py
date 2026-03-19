def check_market_quality(packet, settings):
    # tuned paper thresholds (modest loosening)
    return {
        "freshness_ok": packet.features.quality.freshness_score >= settings.min_freshness_score,
        "liquidity_ok": packet.features.quality.liquidity_score >= settings.min_liquidity_score,
        "volatility_ok": packet.features.volatility.rv_1h <= settings.max_volatility_rv_1h,
        "contradiction_ok": packet.ml_scores.contradiction_score <= settings.max_contradiction,
        "crowdedness_ok": packet.ml_scores.crowdedness_score <= settings.max_crowdedness,
        "extension_ok": packet.ml_scores.extension_score <= settings.max_extension,
        "cooldown_ok": not packet.policy_context.cooldown_active,
    }
