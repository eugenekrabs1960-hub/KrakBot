from datetime import datetime, timezone

from app.schemas.decision_output import DecisionOutput
from app.schemas.feature_packet import FeaturePacket
from app.services.models.adapter_base import LocalModelAdapter


class QwenLocalAdapter(LocalModelAdapter):
    def analyze(self, packet: FeaturePacket) -> DecisionOutput:
        """Confidence-semantics pass (narrow):
        - keep strict breakout discipline
        - remove broad no-trade inflation
        - make confidence bands explicit and meaningful
        """
        m = packet.features.returns.momentum_score
        t = packet.ml_scores.tradability_score
        contradiction = packet.ml_scores.contradiction_score
        extension = packet.ml_scores.extension_score
        fragility = packet.ml_scores.fragility_score
        freshness = packet.features.quality.freshness_score
        liq = packet.features.quality.liquidity_score
        rv = packet.features.volatility.rv_1h
        breakout = packet.features.structure.breakout_state
        align = packet.features.trend.trend_alignment_score
        trend_q = packet.features.trend.trend_quality_score

        # base directional decision unchanged
        action = "long" if m > 0.2 else ("short" if m < -0.2 else "no_trade")

        # strict breakout gate retained
        breakout_strong = (
            breakout == "confirmed" and
            abs(m) >= 0.45 and
            align >= 0.55 and
            trend_q >= 0.55 and
            contradiction <= 0.45 and
            extension <= 0.60 and
            freshness >= 0.45 and
            liq >= 0.30
        )

        # strategy identity tuning: mean-reversion-first, trend continuation stricter
        trend_continuation_strong = (
            abs(m) >= 0.60 and
            abs(align) >= 0.74 and
            trend_q >= 0.72 and
            contradiction <= 0.32 and
            extension <= 0.48 and
            freshness >= 0.48 and
            fragility <= 0.38
        )

        if action == "no_trade":
            setup_type = "unclear"
        elif breakout_strong:
            setup_type = "breakout_confirmation"
        elif trend_continuation_strong:
            setup_type = "trend_continuation"
        else:
            setup_type = "mean_reversion"

        # confidence semantics (explicit bands)
        edge = 0.45 * abs(m) + 0.35 * t + 0.20 * max(0.0, 1.0 - contradiction)
        risk = (
            0.35 * contradiction +
            0.25 * extension +
            0.20 * max(0.0, 1.0 - freshness) +
            0.20 * fragility
        )
        score = edge - 0.30 * risk

        clean = (contradiction <= 0.35 and extension <= 0.50 and freshness >= 0.55 and fragility <= 0.40 and t >= 0.50)
        tradable = (contradiction <= 0.70 and extension <= 0.80 and freshness >= 0.30 and t >= 0.30)

        if action == "no_trade":
            conf = min(0.38, max(0.20, 0.24 + 0.20 * max(0.0, score)))
        else:
            # high confidence intentionally rare: requires strong edge + very clean context + robust setup evidence
            high_eligible = (
                clean and
                abs(m) >= 0.68 and
                t >= 0.62 and
                contradiction <= 0.28 and
                extension <= 0.42 and
                freshness >= 0.62 and
                fragility <= 0.30 and
                (
                    breakout_strong or
                    (abs(align) >= 0.72 and trend_q >= 0.70)
                )
            )

            if high_eligible:
                conf = min(0.82, max(0.72, 0.72 + 0.16 * max(0.0, score)))
            elif tradable:
                conf = min(0.69, max(0.45, 0.52 + 0.20 * score))  # mid for imperfect but tradable
            else:
                conf = min(0.44, max(0.25, 0.34 + 0.15 * score))  # low for weak-edge cases

        uncertainty = min(0.95, max(0.05, 1.0 - conf + 0.20 * risk))

        thesis = (
            f"{packet.coin} {action} on {packet.decision_context.primary_horizon}: "
            f"mom={m:.2f}, tradability={t:.2f}, contradiction={contradiction:.2f}, "
            f"extension={extension:.2f}, freshness={freshness:.2f}, fragility={fragility:.2f}."
        )

        reasons = [
            {
                "label": "momentum_alignment",
                "strength": min(1.0, abs(m)),
                "explanation": f"momentum_score={m:.2f}",
            },
            {
                "label": "execution_quality",
                "strength": t,
                "explanation": f"tradability_score={t:.2f}",
            },
        ]
        if breakout_strong:
            reasons.append(
                {
                    "label": "validated_breakout",
                    "strength": 0.82,
                    "explanation": "breakout confirmed with strong alignment and controlled risk",
                }
            )
        else:
            reasons.append(
                {
                    "label": "trend_quality",
                    "strength": trend_q,
                    "explanation": f"trend_quality_score={trend_q:.2f}",
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
        if freshness < 0.45:
            risks.append(
                {
                    "label": "freshness_risk",
                    "severity": 1 - freshness,
                    "explanation": f"freshness_score={freshness:.2f}",
                }
            )
        if fragility > 0.45:
            risks.append(
                {
                    "label": "fragility_risk",
                    "severity": min(1.0, fragility),
                    "explanation": f"fragility_score={fragility:.2f}",
                }
            )
        if rv > 0.8:
            risks.append(
                {
                    "label": "high_realized_volatility",
                    "severity": min(1.0, rv),
                    "explanation": f"rv_1h={rv:.2f}",
                }
            )

        inv = None
        if action in {"long", "short"}:
            inv = {
                "type": "thesis_failure",
                "value": None,
                "reason": "momentum weakens and contradiction/extension risk rises",
            }

        evidence_used = [
            "features.returns.momentum_score",
            "ml_scores.tradability_score",
            "ml_scores.contradiction_score",
            "ml_scores.extension_score",
            "features.quality.freshness_score",
            "ml_scores.fragility_score",
            "features.trend.trend_alignment_score",
            "features.trend.trend_quality_score",
            "features.structure.breakout_state",
        ]

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
                {"action": "no_trade", "reason": "if edge is weak or continuation quality is insufficient"},
                {"action": "long" if action == "short" else "short", "reason": "if momentum flips with better setup quality"},
            ],
            execution_preference={
                "urgency": "normal" if action != "no_trade" else "low",
                "entry_style_hint": "market_or_aggressive_limit" if action != "no_trade" else "none",
            },
        )
