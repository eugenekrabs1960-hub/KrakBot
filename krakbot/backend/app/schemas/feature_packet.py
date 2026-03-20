from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class DecisionContext(BaseModel):
    decision_horizons: list[str] = ["15m", "1h", "4h"]
    primary_horizon: str = "1h"
    allowed_actions: list[str] = ["long", "short", "no_trade"]
    mode: Literal["paper", "live_hyperliquid"] = "paper"


class MarketSnapshot(BaseModel):
    last_price: float
    mark_price: float
    index_price: float
    spread_bps: float
    volume_5m_usd: float
    volume_1h_usd: float
    open_interest_usd: float
    funding_rate: float


class ReturnsFeatures(BaseModel):
    ret_1m: float
    ret_5m: float
    ret_15m: float
    ret_1h: float
    ret_4h: float
    momentum_score: float
    acceleration_score: float


class VolatilityFeatures(BaseModel):
    rv_5m: float
    rv_15m: float
    rv_1h: float
    volatility_state: str


class TrendFeatures(BaseModel):
    trend_5m: Literal["up", "down", "flat"]
    trend_15m: Literal["up", "down", "flat"]
    trend_1h: Literal["up", "down", "flat"]
    trend_4h: Literal["up", "down", "flat"]
    trend_alignment_score: float
    trend_quality_score: float


class VolumeFeatures(BaseModel):
    volume_zscore_5m: float
    volume_zscore_1h: float
    volume_acceleration: float


class OrderbookFeatures(BaseModel):
    imbalance_10bp: float
    imbalance_25bp: float
    micro_pressure_score: float
    book_depth_score: float
    slippage_estimate_bps: float


class DerivativesFeatures(BaseModel):
    oi_change_5m: float
    oi_change_15m: float
    oi_change_1h: float
    funding_state: str


class StructureFeatures(BaseModel):
    distance_from_1h_high: float
    distance_from_1h_low: float
    distance_from_4h_high: float
    distance_from_4h_low: float
    breakout_state: str


class QualityFeatures(BaseModel):
    liquidity_score: float
    freshness_score: float
    data_completeness_score: float
    source_health_score: float


class Features(BaseModel):
    returns: ReturnsFeatures
    volatility: VolatilityFeatures
    trend: TrendFeatures
    volume: VolumeFeatures
    orderbook: OrderbookFeatures
    derivatives: DerivativesFeatures
    structure: StructureFeatures
    quality: QualityFeatures


class MLScores(BaseModel):
    attention_score: float
    opportunity_score: float
    tradability_score: float
    market_regime: str
    regime_compatibility_score: float
    move_probability_up_15m: float
    move_probability_down_15m: float
    move_probability_up_1h: float
    move_probability_down_1h: float
    trade_quality_prior: float
    no_trade_prior: float
    contradiction_score: float
    crowdedness_score: float
    extension_score: float
    fragility_score: float


class ChangeSummary(BaseModel):
    largest_feature_changes: list[str] = []
    new_risks: list[str] = []


class OptionalSignals(BaseModel):
    wallet_summary: dict | None = None
    # note: priced_in_risk_score inside news_summary is hybrid (news + market microstructure), not pure RSS
    news_summary: dict | None = None
    social_summary: dict | None = None


class PolicyContext(BaseModel):
    current_open_positions: int
    max_open_positions: int
    max_notional_per_trade: float
    max_total_notional: float
    cooldown_active: bool


class FeaturePacket(BaseModel):
    packet_version: str = "1.0"
    packet_id: str
    generated_at: datetime
    coin: str
    symbol: str
    decision_context: DecisionContext
    market_snapshot: MarketSnapshot
    features: Features
    ml_scores: MLScores
    change_summary: ChangeSummary
    optional_signals: OptionalSignals
    policy_context: PolicyContext
