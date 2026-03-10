"""EIF (Explainable Intelligence Framework) Phase 1 locked vocabulary artifacts."""

REGIME_VERSION = "v1"
REASON_CODE_VERSION = "v1"
TAG_DICTIONARY_VERSION = "v1"

REGIME_DIMENSIONS = {
    "trend": ["up", "down", "flat", "unknown"],
    "volatility": ["high", "normal", "low", "unknown"],
    "liquidity": ["thick", "normal", "thin", "unknown"],
    "session_structure": ["active", "quiet", "unknown"],
}

FILTER_EVENT_TYPES = ["decision"]
FILTER_DECISIONS = ["enter", "exit", "hold", "unknown"]
TRADE_CONTEXT_EVENT_TYPES = ["decision", "entry", "exit", "skip", "order_attempt", "order_result", "unknown"]

FILTER_REASON_CODES = {
    "decision": [
        "ok",
        "bot_not_running",
        "strategy_disabled",
        "hold_decision",
        "no_market_trade_price",
        "paper_only_guard",
        "min_interval_guard",
        "per_minute_rate_limit",
        "data_stale",
        "min_activity_fail",
        "spread_too_wide",
        "volatility_out_of_band",
        "depth_too_thin",
        "imbalance_direction_mismatch",
        "regime_strategy_mismatch",
        "cooldown_active",
        "filter_eval_error",
        "shadow_data_stale",
        "shadow_min_activity_fail",
        "shadow_spread_too_wide",
        "shadow_volatility_out_of_band",
        "shadow_depth_too_thin",
        "shadow_imbalance_direction_mismatch",
        "shadow_regime_strategy_mismatch",
        "shadow_cooldown_active",
        "unknown",
    ],
    "skip": [
        "min_interval_guard",
        "per_minute_rate_limit",
        "bot_not_running",
        "hold_decision",
        "strategy_disabled",
        "qty_non_positive",
        "unknown",
    ],
}

TRADE_CONTEXT_TAGS = {
    "mode": ["paper", "live", "test"],
    "event": ["decision", "entry", "exit", "skip", "order_attempt", "order_result"],
    "source": ["live_paper_test_mode", "api_paper_order", "system"],
    "risk": ["guarded", "normal", "unknown"],
}

SAFE_UNKNOWN_REASON_CODE = "unknown"
SAFE_UNKNOWN_DECISION = "unknown"
SAFE_FILTER_EVENT_TYPE = "decision"
SAFE_TRADE_EVENT_TYPE = "unknown"
SAFE_UNKNOWN_TAG = "risk:unknown"
