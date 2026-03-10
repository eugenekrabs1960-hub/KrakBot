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

    # EIF Phase 1 feature flags (safe defaults: off)
    eif_capture_enabled: bool = False
    eif_scorecard_compute_enabled: bool = False
    live_paper_test_market: str = "SOL/USD"
    live_paper_test_loop_interval_sec: float = 5.0
    live_paper_test_order_qty: float = 0.05
    live_paper_test_max_orders_per_minute: int = 6
    live_paper_test_min_seconds_between_orders: float = 5.0
    live_paper_test_force_paper_only: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
