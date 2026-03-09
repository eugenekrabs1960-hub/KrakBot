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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
