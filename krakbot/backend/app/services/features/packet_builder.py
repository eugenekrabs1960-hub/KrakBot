from datetime import datetime, timezone
import uuid

from app.schemas.feature_packet import FeaturePacket

_LAST_NUMERIC_BY_COIN: dict[str, dict[str, float]] = {}


def _snapshot_numeric(features: dict, ml_scores: dict) -> dict[str, float]:
    return {
        "ret_1m": float(features["returns"]["ret_1m"]),
        "ret_5m": float(features["returns"]["ret_5m"]),
        "momentum_score": float(features["returns"]["momentum_score"]),
        "rv_1h": float(features["volatility"]["rv_1h"]),
        "liquidity_score": float(features["quality"]["liquidity_score"]),
        "attention_score": float(ml_scores["attention_score"]),
        "opportunity_score": float(ml_scores["opportunity_score"]),
        "tradability_score": float(ml_scores["tradability_score"]),
        "trade_quality_prior": float(ml_scores["trade_quality_prior"]),
        "regime_compatibility_score": float(ml_scores["regime_compatibility_score"]),
        "contradiction_score": float(ml_scores["contradiction_score"]),
        "extension_score": float(ml_scores["extension_score"]),
    }


def _build_change_summary(coin: str, features: dict, ml_scores: dict) -> dict:
    current = _snapshot_numeric(features, ml_scores)
    prev = _LAST_NUMERIC_BY_COIN.get(coin)
    _LAST_NUMERIC_BY_COIN[coin] = current

    if not prev:
        return {
            "largest_feature_changes": ["baseline_packet_no_prior_delta"],
            "new_risks": [],
        }

    deltas = []
    for k, v in current.items():
        dv = v - prev.get(k, 0.0)
        deltas.append((k, dv, abs(dv)))
    deltas.sort(key=lambda x: x[2], reverse=True)

    largest = [f"{k}:{dv:+.4f}" for k, dv, _ in deltas[:3]]
    risks = []
    if current["contradiction_score"] > 0.7 and prev.get("contradiction_score", 0) <= 0.7:
        risks.append("contradiction_crossed_high")
    if current["extension_score"] > 0.85 and prev.get("extension_score", 0) <= 0.85:
        risks.append("extension_crossed_high")
    if current["liquidity_score"] < 0.25 and prev.get("liquidity_score", 1) >= 0.25:
        risks.append("liquidity_dropped_below_threshold")
    if current["rv_1h"] > 0.85 and prev.get("rv_1h", 0) <= 0.85:
        risks.append("volatility_regime_heating_up")
    if current["trade_quality_prior"] < 0.40 and prev.get("trade_quality_prior", 1) >= 0.40:
        risks.append("asymmetry_quality_degraded")
    if current["regime_compatibility_score"] < 0.45 and prev.get("regime_compatibility_score", 1) >= 0.45:
        risks.append("regime_compatibility_degraded")

    return {
        "largest_feature_changes": largest,
        "new_risks": risks,
    }


def build_feature_packet(coin: str, mode: str, market_snapshot: dict, features: dict, ml_scores: dict, policy_context: dict) -> FeaturePacket:
    return FeaturePacket(
        packet_id=f"pkt_{uuid.uuid4().hex[:12]}",
        generated_at=datetime.now(timezone.utc),
        coin=coin,
        symbol=market_snapshot["symbol"],
        decision_context={
            "decision_horizons": ["15m", "1h", "4h"],
            "primary_horizon": "1h",
            "allowed_actions": ["long", "short", "no_trade"],
            "mode": mode,
        },
        market_snapshot=market_snapshot,
        features=features,
        ml_scores=ml_scores,
        change_summary=_build_change_summary(coin, features, ml_scores),
        optional_signals={"wallet_summary": None, "news_summary": None, "social_summary": None},
        policy_context=policy_context,
    )
