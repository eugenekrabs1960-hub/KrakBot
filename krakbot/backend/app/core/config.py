from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Krakbot Control Plane"
    env: str = "dev"
    database_url: str = "postgresql+psycopg://krakbot:krakbot@postgres:5432/krakbot"
    redis_url: str = "redis://redis:6379/0"

    # MVP defaults
    default_venue: str = "kraken"
    enabled_markets: str = "SOL/USD"
    instrument_type: str = "spot"

    # Live paper test mode (safe defaults: off)
    live_paper_test_mode_enabled: bool = False

    # EIF feature flags (safe defaults: off)
    eif_capture_enabled: bool = False
    eif_scorecard_compute_enabled: bool = False
    eif_filter_shadow_mode: bool = False
    eif_filter_enforce_mode: bool = False
    eif_filter_fail_closed: bool = False
    eif_analytics_api_enabled: bool = False

    # EIF filter thresholds (MVP defaults)
    eif_filter_max_data_age_ms: int = 120000
    eif_filter_min_qty_5m: float = 15.0
    eif_filter_min_trade_count_window: int = 10
    eif_filter_max_spread_pct: float = 0.01
    eif_filter_min_volatility_pct: float = 0.001
    eif_filter_max_volatility_pct: float = 0.05
    eif_filter_min_depth_qty: float = 3.0
    eif_filter_depth_levels: int = 5
    eif_filter_min_imbalance_abs: float = 0.25
    eif_filter_cooldown_consecutive_losses: int = 3
    eif_filter_drawdown_shock_pct: float = 12.0
    live_paper_test_market: str = "SOL/USD"
    live_paper_test_loop_interval_sec: float = 5.0
    live_paper_test_order_qty: float = 0.05
    live_paper_test_max_orders_per_minute: int = 6
    live_paper_test_min_seconds_between_orders: float = 5.0
    live_paper_test_force_paper_only: bool = True
    live_paper_test_max_active_strategies: int = 3

    # Wallet Intelligence Benchmark (WIB) phase-2 settings
    wallet_intel_helius_api_key: str = ""
    wallet_intel_helius_base_url: str = "https://api.helius.xyz"
    wallet_intel_solana_watchlist: str = ""
    wallet_intel_default_price_ref_usd: float = 85.0
    wallet_intel_min_t1_events_30d: int = 20
    wallet_intel_min_active_days_30d: int = 10
    wallet_intel_min_notional_30d: float = 25000.0
    wallet_intel_min_sol_relevance: float = 0.8
    wallet_intel_recency_days: int = 5
    wallet_intel_cohort_target_size: int = 50
    wallet_intel_cohort_hysteresis_buffer: int = 15
    wallet_intel_alignment_min_confidence: float = 35.0
    wallet_intel_helius_page_limit: int = 100
    wallet_intel_helius_max_pages_per_run: int = 3
    wallet_intel_helius_retry_attempts: int = 4
    wallet_intel_helius_retry_backoff_ms: int = 300
    wallet_intel_scheduler_enabled: bool = False
    wallet_intel_scheduler_interval_sec: int = 900
    wallet_intel_scheduler_lock_ttl_sec: int = 1200

    # Hyperliquid execution settings
    hyperliquid_enabled: bool = False
    hyperliquid_base_url: str = "https://api.hyperliquid.xyz"
    hyperliquid_environment: str = "testnet"
    hyperliquid_account_address: str = ""
    hyperliquid_api_wallet: str = ""
    hyperliquid_market_collector_enabled: bool = False
    hyperliquid_market_collector_interval_sec: int = 60
    hyperliquid_market_collector_symbols_limit: int = 200

    # Jason agent (OpenAI-driven)
    openai_api_key: str = ""
    jason_agent_model: str = "gpt-5.4"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
