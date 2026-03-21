from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "KrakBot AI Trading Lab"
    env: str = "dev"
    database_url: str = "postgresql+psycopg://krakbot:krakbot@localhost:5432/krakbot"

    # defaults requested
    tracked_coins_default: str = "BTC,ETH,SOL"
    wildcard_pool_default: str = "XRP,DOGE,ADA,AVAX,LINK"
    wildcard_slots_default: int = 2
    wildcard_reeval_minutes_default: int = 30
    wildcard_min_hold_minutes_default: int = 60
    wildcard_replace_threshold_default: float = 0.08
    feature_refresh_seconds: int = 60
    decision_cycle_seconds: int = 300
    decision_cycle_hard_timeout_sec: int = 40
    top_candidates_per_cycle: int = 3

    execution_mode_default: str = "paper"
    trading_enabled_default: bool = True
    live_armed_default: bool = False

    fixed_notional_usd: float = 50.0
    no_pyramiding: bool = True
    max_open_positions: int = 3
    max_total_notional: float = 300.0
    paper_material_position_qty_threshold: float = 0.75
    leverage_cap: float = 3.0
    allow_long: bool = True
    allow_short: bool = True
    # runtime-selectivity knob (no-op unless raised): mean_reversion confidence floor for allow_trade
    mean_reversion_min_confidence: float = 0.0

    # policy thresholds
    max_spread_bps: float = 12.0
    min_liquidity_score: float = 0.20
    min_freshness_score: float = 0.30
    max_volatility_rv_1h: float = 0.95
    max_contradiction: float = 0.85
    max_crowdedness: float = 0.85
    max_extension: float = 0.90
    max_fragility: float = 0.85
    freshness_threshold_sec: int = 90

    local_model_name: str = "Qwen3.5-9B-Q4_K_M.gguf"
    local_model_context_limit: int = 32000
    local_model_max_tokens: int = 1200
    local_model_temperature: float = 0.21
    prompt_version: str = "local_analyst_v1"
    repair_enabled: bool = True

    local_model_base_url: str = "http://10.50.0.30:8000"
    # alias supports existing env naming in compose
    local_model_api_key: str = Field(default="", validation_alias="QWEN_LOCAL_API_KEY")
    local_model_timeout_sec: int = 15

    # paper account ops
    paper_starting_equity_usd: float = 10000.0
    paper_maker_fee_bps: float = 2.0
    paper_taker_fee_bps: float = 5.0

    # lockdown controls
    external_api_enabled: bool = False
    auto_loops_enabled: bool = False

    # controlled news summary path (single source, compact)
    news_signal_enabled: bool = True
    news_signal_source_url: str = "https://feeds.feedburner.com/CoinDesk"
    news_signal_ttl_sec: int = 300

    # controlled community heat signal (daily attention/sentiment summary)
    community_signal_enabled: bool = True
    community_signal_source_url: str = "https://api.coingecko.com/api/v3/search/trending"
    community_signal_ttl_sec: int = 900

    # low-pressure experiment runner guardrails
    experiment_cycle_delay_sec: float = 0.35
    experiment_abort_on_model_offline: bool = True

    # trading loop model-offline backoff/cooldown
    model_offline_cooldown_sec: int = 60
    model_offline_backoff_max_sec: int = 300

    # trading-mode 1m history seeding (official Hyperliquid candle snapshot)
    trading_history_seed_lookback_minutes: int = 360
    trading_history_seed_min_points: int = 90

    # LLM runtime safeguards
    llm_max_concurrent_requests: int = 1
    llm_request_timeout_sec: int = 12
    llm_disable_repair: bool = True
    llm_safe_mode: bool = True
    llm_safe_mode_max_candidates: int = 1


    # Jason supervisor loop (disabled by default)
    jason_loop_enabled: bool = False
    jason_loop_interval_sec: int = 60
    jason_agent_model: str = "gpt-5.4"

    # autonomy core chunk-1 controls
    autonomy_core_enabled: bool = False
    autonomy_promotion_monitor_enabled: bool = False
    autonomy_promotion_monitor_interval_sec: int = 120
    autonomy_one_change_lock_ttl_sec: int = 900
    autonomy_rollback_cooldown_sec: int = 1800

    hyperliquid_account_address: str = ""
    hyperliquid_order_relay_url: str = ""
    hyperliquid_order_relay_token: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
