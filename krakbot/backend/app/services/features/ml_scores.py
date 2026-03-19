def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def compute_ml_scores(features: dict) -> dict:
    # core raw signals
    r = features["returns"]
    t = features["trend"]
    v = features["volatility"]
    q = features["quality"]
    ob = features["orderbook"]
    st = features["structure"]
    der = features["derivatives"]

    m = float(r["momentum_score"])
    ret_1m = float(r["ret_1m"])
    ret_5m = float(r["ret_5m"])
    ret_15m = float(r["ret_15m"])
    ret_1h = float(r["ret_1h"])

    align = float(t["trend_alignment_score"])
    trend_q = float(t["trend_quality_score"])

    rv_1h = float(v["rv_1h"])
    liq = float(q["liquidity_score"])
    fresh = float(q["freshness_score"])
    src = float(q["source_health_score"])

    micro = float(ob["micro_pressure_score"])
    depth = float(ob["book_depth_score"])
    slip = float(ob["slippage_estimate_bps"])

    oi1h = float(der["oi_change_1h"])
    funding_state = str(der["funding_state"])

    d1h_hi = float(st["distance_from_1h_high"])
    d1h_lo = float(st["distance_from_1h_low"])
    d4h_hi = float(st["distance_from_4h_high"])
    d4h_lo = float(st["distance_from_4h_low"])
    breakout_state = str(st["breakout_state"])

    # discriminator 1: trend cleanliness vs noisy continuation
    short_vs_mid_conflict = abs(ret_1m - ret_15m)
    mid_vs_swing_conflict = abs(ret_5m - ret_1h)
    horizon_conflict = clamp(8.0 * short_vs_mid_conflict + 6.0 * mid_vs_swing_conflict)

    trend_cleanliness = clamp(
        0.35 * abs(m) +
        0.30 * align +
        0.20 * trend_q +
        0.15 * (1.0 - rv_1h)
    )

    # discriminator 2: breakout quality vs weak breakout
    near_key_level = clamp(1.0 - min(d1h_hi, d1h_lo) / 0.05)
    near_swing_level = clamp(1.0 - min(d4h_hi, d4h_lo) / 0.10)
    breakout_flag = 1.0 if breakout_state == "confirmed" else (0.55 if breakout_state == "attempt" else 0.0)
    breakout_quality = clamp(
        0.35 * breakout_flag +
        0.20 * near_key_level +
        0.15 * near_swing_level +
        0.15 * clamp(micro) +
        0.15 * clamp(depth)
    )

    # discriminator 3: asymmetry quality (good vs poor)
    directional_edge = clamp(abs(m))
    execution_edge = clamp(0.55 * liq + 0.45 * (1.0 - slip / 25.0))
    asymmetry_quality = clamp(0.60 * directional_edge + 0.40 * execution_edge)

    # discriminator 4: conflict/crowding/extension/fragility
    contradiction = clamp(0.70 * horizon_conflict + 0.30 * (1.0 - align))

    funding_crowd = 0.65 if funding_state == "positive" else (0.35 if funding_state == "neutral" else 0.55)
    crowdedness = clamp(0.50 * abs(oi1h) + 0.30 * funding_crowd + 0.20 * abs(float(ob["imbalance_25bp"])))

    # extension rises near range extremes + large 1h move
    level_extension = clamp(1.0 - min(d1h_hi, d1h_lo) / 0.03)
    return_extension = clamp(abs(ret_1h) / 0.05)
    extension = clamp(0.60 * level_extension + 0.40 * return_extension)

    fragility = clamp(0.45 * (1.0 - fresh) + 0.35 * (1.0 - src) + 0.20 * rv_1h)

    # aggregate meta scores
    attention = clamp(0.35 * asymmetry_quality + 0.35 * trend_cleanliness + 0.30 * breakout_quality)
    opportunity = clamp(0.40 * asymmetry_quality + 0.35 * breakout_quality + 0.25 * (1.0 - contradiction))
    tradability = clamp(0.45 * liq + 0.35 * (1.0 - slip / 25.0) + 0.20 * (1.0 - rv_1h))

    market_regime = "trend" if trend_cleanliness >= 0.58 else ("breakout" if breakout_quality >= 0.62 else "range")
    regime_compat = clamp(
        0.45 * trend_cleanliness +
        0.35 * breakout_quality +
        0.20 * (1.0 - contradiction)
    )

    up15 = clamp(0.5 + 0.20 * m - 0.10 * contradiction)
    dn15 = clamp(1.0 - up15)
    up1h = clamp(0.5 + 0.24 * m - 0.12 * contradiction - 0.08 * extension)
    dn1h = clamp(1.0 - up1h)

    trade_quality_prior = clamp(
        0.35 * asymmetry_quality +
        0.25 * trend_cleanliness +
        0.20 * breakout_quality +
        0.20 * (1.0 - contradiction)
    )
    no_trade_prior = clamp(1.0 - trade_quality_prior)

    return {
        "attention_score": attention,
        "opportunity_score": opportunity,
        "tradability_score": tradability,
        "market_regime": market_regime,
        "regime_compatibility_score": regime_compat,
        "move_probability_up_15m": up15,
        "move_probability_down_15m": dn15,
        "move_probability_up_1h": up1h,
        "move_probability_down_1h": dn1h,
        "trade_quality_prior": trade_quality_prior,
        "no_trade_prior": no_trade_prior,
        "contradiction_score": contradiction,
        "crowdedness_score": crowdedness,
        "extension_score": extension,
        "fragility_score": fragility,
    }
