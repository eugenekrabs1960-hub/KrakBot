from datetime import datetime, timezone
import uuid

from app.schemas.feature_packet import FeaturePacket


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
        change_summary={"largest_feature_changes": [], "new_risks": []},
        optional_signals={"wallet_summary": None, "news_summary": None, "social_summary": None},
        policy_context=policy_context,
    )
