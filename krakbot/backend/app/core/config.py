from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "KrakBot AI Trading Lab"
    env: str = "dev"
    database_url: str = "postgresql+psycopg://krakbot:krakbot@localhost:5432/krakbot"

    # defaults requested
    tracked_coins_default: str = "BTC,ETH,SOL"
    feature_refresh_seconds: int = 60
    decision_cycle_seconds: int = 300
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

    # policy thresholds (paper tuning pass: modest loosening)
    max_spread_bps: float = 12.0
    min_liquidity_score: float = 0.20  # was 0.25
    min_freshness_score: float = 0.30  # new; was hardcoded 0.40
    max_volatility_rv_1h: float = 0.95  # was hardcoded 0.90
    max_contradiction: float = 0.85  # was 0.70
    max_crowdedness: float = 0.85  # was 0.80
    max_extension: float = 0.90  # was 0.85
    max_fragility: float = 0.85
    freshness_threshold_sec: int = 90

    local_model_name: str = "Qwen3.5-9B"
    local_model_context_limit: int = 32000
    local_model_max_tokens: int = 1200
    local_model_temperature: float = 0.2
    prompt_version: str = "local_analyst_v1"
    repair_enabled: bool = True

    local_model_base_url: str = "http://10.50.0.30:8000"
    local_model_api_key: str = ""
    local_model_timeout_sec: int = 20

    hyperliquid_account_address: str = ""
    hyperliquid_order_relay_url: str = ""
    hyperliquid_order_relay_token: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
