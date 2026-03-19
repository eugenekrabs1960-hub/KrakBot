from datetime import datetime, timezone

from app.schemas.decision_output import DecisionOutput
from app.schemas.feature_packet import FeaturePacket
from app.services.models.adapter_base import LocalModelAdapter


class QwenLocalAdapter(LocalModelAdapter):
    def analyze(self, packet: FeaturePacket) -> DecisionOutput:
        """Narrow prompt/output improvement pass:
        produce evidence-specific reasons/risks while staying deterministic.
        """
        m = packet.features.returns.momentum_score
        t = packet.ml_scores.tradability_score
        contradiction = packet.ml_scores.contradiction_score
        extension = packet.ml_scores.extension_score
        liq = packet.features.quality.liquidity_score
        rv = packet.features.volatility.rv_1h
        breakout = packet.features.structure.breakout_state

        # action choice remains conservative
        action = "long" if m > 0.2 else ("short" if m < -0.2 else "no_trade")

        if action == "no_trade":
            setup_type = "unclear"
        elif breakout == "confirmed":
            setup_type = "breakout_confirmation"
        elif abs(packet.features.trend.trend_alignment_score) > 0.65:
            setup_type = "trend_continuation"
        else:
            setup_type = "mean_reversion"

        conf = min(0.92, max(0.30, 0.45 * abs(m) + 0.35 * t + 0.20 * (1 - min(1.0, contradiction))))
        uncertainty = min(0.95, max(0.05, 1 - conf + 0.15 * extension))

        thesis = (
            f"{packet.coin} {action} on {packet.decision_context.primary_horizon}: "
            f"momentum={m:.2f}, tradability={t:.2f}, contradiction={contradiction:.2f}, breakout={breakout}."
        )

        reasons = [
            {
                "label": "momentum_alignment",
                "strength": min(1.0, abs(m)),
                "explanation": f"momentum_score={m:.2f} supports directional bias",
            },
            {
                "label": "execution_quality",
                "strength": t,
                "explanation": f"tradability_score={t:.2f} from liquidity/slippage context",
            },
        ]

        # Add one packet-specific supplemental reason for richer diagnostics
        if breakout in {"attempt", "confirmed"}:
            reasons.append(
                {
                    "label": "structure_breakout_context",
                    "strength": 0.65 if breakout == "attempt" else 0.8,
                    "explanation": f"breakout_state={breakout}",
                }
            )
        else:
            reasons.append(
                {
                    "label": "trend_quality",
                    "strength": packet.features.trend.trend_quality_score,
                    "explanation": f"trend_quality_score={packet.features.trend.trend_quality_score:.2f}",
                }
            )

        risks = [
            {
                "label": "regime_contradiction",
                "severity": min(1.0, contradiction),
                "explanation": f"contradiction_score={contradiction:.2f}",
            },
            {
                "label": "extension_risk",
                "severity": min(1.0, extension),
                "explanation": f"extension_score={extension:.2f}",
            },
        ]
        if rv > 0.8:
            risks.append(
                {
                    "label": "high_realized_volatility",
                    "severity": min(1.0, rv),
                    "explanation": f"rv_1h={rv:.2f}",
                }
            )
        if liq < 0.3:
            risks.append(
                {
                    "label": "thin_liquidity",
                    "severity": 1 - liq,
                    "explanation": f"liquidity_score={liq:.2f}",
                }
            )

        inv = None
        if action in {"long", "short"}:
            inv = {
                "type": "thesis_failure",
                "value": None,
                "reason": "momentum alignment decays and contradiction rises",
            }

        evidence_used = [
            "features.returns.momentum_score",
            "ml_scores.tradability_score",
            "ml_scores.contradiction_score",
            "ml_scores.extension_score",
            "features.structure.breakout_state",
        ]
        if rv > 0.8:
            evidence_used.append("features.volatility.rv_1h")

        return DecisionOutput(
            packet_id=packet.packet_id,
            generated_at=datetime.now(timezone.utc),
            model_name="Qwen3.5-9B",
            coin=packet.coin,
            symbol=packet.symbol,
            action=action,
            setup_type=setup_type,
            horizon=packet.decision_context.primary_horizon,
            confidence=conf,
            uncertainty=uncertainty,
            thesis_summary=thesis,
            reasons=reasons[:4],
            risks=risks[:4],
            invalidation=inv,
            targets={
                "take_profit_hint": None,
                "expected_move_magnitude": "small" if action != "no_trade" else "null",
            },
            evidence_used=evidence_used,
            evidence_ignored=["optional_signals.news_summary", "optional_signals.social_summary"],
            alternatives_considered=[
                {"action": "no_trade", "reason": "if contradiction rises or liquidity weakens"},
                {"action": "long" if action == "short" else "short", "reason": "if momentum flips sign"},
            ],
            execution_preference={
                "urgency": "normal" if action != "no_trade" else "low",
                "entry_style_hint": "market_or_aggressive_limit" if action != "no_trade" else "none",
            },
        )
