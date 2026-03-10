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

FILTER_REASON_CODES = {
    "decision": [
        "ok",
        "bot_not_running",
        "strategy_disabled",
        "hold_decision",
        "no_market_trade_price",
        "paper_only_guard",
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
