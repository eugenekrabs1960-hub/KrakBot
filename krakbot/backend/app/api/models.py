from app.schemas.settings import SettingsBundle, ModeSettings, UniverseSettings, LoopSettings, ModelSettings, RiskSettings
from app.core.config import settings as cfg


runtime_settings = SettingsBundle(
    mode=ModeSettings(
        execution_mode=cfg.execution_mode_default,
        trading_enabled=cfg.trading_enabled_default,
        live_armed=cfg.live_armed_default,
        emergency_stop=False,
    ),
    universe=UniverseSettings(
        tracked_coins=[c.strip() for c in cfg.tracked_coins_default.split(',') if c.strip()],
        max_candidates_per_cycle=cfg.top_candidates_per_cycle,
        core_coins=[c.strip() for c in cfg.tracked_coins_default.split(',') if c.strip()][:3],
        wildcard_pool=[c.strip() for c in cfg.wildcard_pool_default.split(',') if c.strip()],
        wildcard_slots=cfg.wildcard_slots_default,
        wildcard_reeval_minutes=cfg.wildcard_reeval_minutes_default,
        wildcard_min_hold_minutes=cfg.wildcard_min_hold_minutes_default,
        wildcard_replace_threshold=cfg.wildcard_replace_threshold_default,
    ),
    loop=LoopSettings(
        feature_refresh_seconds=cfg.feature_refresh_seconds,
        decision_cycle_seconds=cfg.decision_cycle_seconds,
    ),
    model=ModelSettings(
        model_name=cfg.local_model_name,
        context_limit=cfg.local_model_context_limit,
        max_output_tokens=cfg.local_model_max_tokens,
        temperature=cfg.local_model_temperature,
        prompt_version=cfg.prompt_version,
        retry_repair_enabled=cfg.repair_enabled,
    ),
    risk=RiskSettings(
        max_open_positions=cfg.max_open_positions,
        max_notional_per_trade=cfg.fixed_notional_usd,
        max_total_notional=cfg.max_total_notional,
        leverage_cap=cfg.leverage_cap,
        allow_long=cfg.allow_long,
        allow_short=cfg.allow_short,
        no_pyramiding=cfg.no_pyramiding,
        mean_reversion_min_confidence=cfg.mean_reversion_min_confidence,
    ),
)
