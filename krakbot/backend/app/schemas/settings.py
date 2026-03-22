from pydantic import BaseModel


class ModeSettings(BaseModel):
    execution_mode: str = "paper"
    trading_enabled: bool = True
    live_armed: bool = False
    emergency_stop: bool = False


class UniverseSettings(BaseModel):
    tracked_coins: list[str] = ["BTC", "ETH", "SOL"]
    max_candidates_per_cycle: int = 3
    core_coins: list[str] = ["BTC", "ETH", "SOL"]
    wildcard_pool: list[str] = ["XRP", "DOGE", "ADA", "AVAX", "LINK"]
    wildcard_slots: int = 2
    wildcard_reeval_minutes: int = 30
    wildcard_min_hold_minutes: int = 60
    wildcard_replace_threshold: float = 0.08


class LoopSettings(BaseModel):
    feature_refresh_seconds: int = 60
    decision_cycle_seconds: int = 300
    allowed_horizons: list[str] = ["15m", "1h", "4h"]
    primary_horizon: str = "1h"


class ModelSettings(BaseModel):
    model_name: str = "Qwen3.5-9B"
    context_limit: int = 32000
    max_output_tokens: int = 1200
    temperature: float = 0.2
    prompt_version: str = "local_analyst_v1"
    retry_repair_enabled: bool = True


class RiskSettings(BaseModel):
    max_open_positions: int = 8
    max_open_legs: int = 12
    max_notional_per_trade: float = 50.0
    max_total_notional: float = 300.0
    leverage_cap: float = 3.0
    allow_long: bool = True
    allow_short: bool = True
    no_pyramiding: bool = False
    mean_reversion_min_confidence: float = 0.0


class SettingsBundle(BaseModel):
    mode: ModeSettings
    universe: UniverseSettings
    loop: LoopSettings
    model: ModelSettings
    risk: RiskSettings
