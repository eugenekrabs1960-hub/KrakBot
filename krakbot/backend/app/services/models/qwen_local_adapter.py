from datetime import datetime, timezone

from app.schemas.decision_output import DecisionOutput
from app.schemas.feature_packet import FeaturePacket
from app.services.models.adapter_base import LocalModelAdapter


class QwenLocalAdapter(LocalModelAdapter):
    def analyze(self, packet: FeaturePacket) -> DecisionOutput:
        # deterministic placeholder; replace with real local inference call
        m = packet.features.returns.momentum_score
        action = "long" if m > 0.2 else ("short" if m < -0.2 else "no_trade")
        inv = None
        if action in {"long", "short"}:
            inv = {"type": "thesis_failure", "value": None, "reason": "momentum_score flips"}
        return DecisionOutput(
            packet_id=packet.packet_id,
            generated_at=datetime.now(timezone.utc),
            model_name="Qwen3.5-9B",
            coin=packet.coin,
            symbol=packet.symbol,
            action=action,
            setup_type="trend_continuation" if action != "no_trade" else "unclear",
            horizon="1h",
            confidence=min(0.9, max(0.3, abs(m))),
            uncertainty=min(0.9, max(0.1, 1 - abs(m))),
            thesis_summary="Packet-driven setup evaluation",
            reasons=[
                {"label": "momentum", "strength": min(1.0, abs(m)), "explanation": "momentum influence"},
                {"label": "tradability", "strength": packet.ml_scores.tradability_score, "explanation": "liquidity + slippage"},
            ],
            risks=[{"label": "regime_shift", "severity": 0.5, "explanation": "short-term regime can flip"}],
            invalidation=inv,
            targets={"take_profit_hint": None, "expected_move_magnitude": "small" if action != "no_trade" else "null"},
            evidence_used=["features.returns.momentum_score", "ml_scores.tradability_score"],
            evidence_ignored=["optional_signals.news_summary"],
            alternatives_considered=[{"action": "no_trade", "reason": "if signal weakens"}],
            execution_preference={"urgency": "normal", "entry_style_hint": "market_or_aggressive_limit" if action != "no_trade" else "none"},
        )
