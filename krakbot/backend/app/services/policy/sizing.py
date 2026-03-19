def fixed_small_notional(settings, risk_profile: dict) -> float:
    return min(settings.fixed_notional_usd, risk_profile["max_notional_per_trade"])
