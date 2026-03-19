from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskProfile:
    profile_id: str
    max_notional_per_trade_usd: float
    min_confidence: float
    max_spread_bps: float
    max_positions: int


RISK_PROFILES: dict[str, RiskProfile] = {
    "risk.paper.v1": RiskProfile(
        profile_id="risk.paper.v1",
        max_notional_per_trade_usd=500.0,
        min_confidence=0.55,
        max_spread_bps=15.0,
        max_positions=4,
    ),
    "risk.live.tight.v1": RiskProfile(
        profile_id="risk.live.tight.v1",
        max_notional_per_trade_usd=100.0,
        min_confidence=0.7,
        max_spread_bps=8.0,
        max_positions=2,
    ),
}

MODEL_PROFILES: dict[str, dict] = {
    "model.qwen35-9b.local.v1": {
        "model": "Qwen3.5-9B",
        "max_context_tokens": 32000,
        "response_schema": "decision.v1",
        "transport": "local_adapter",
    }
}

SCORE_PROFILES: dict[str, dict] = {
    "score.default.v1": {
        "trend_weight": 0.6,
        "mean_reversion_weight": 0.4,
        "liquidity_target_volume_1m_usd": 2_000_000,
    }
}
