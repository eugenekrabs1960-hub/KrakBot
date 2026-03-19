from __future__ import annotations

from app.lab.contracts import DecisionOutput, EvidenceRef, FeaturePacket, TradeSide


class LocalQwenAnalystAdapter:
    """Local analyst adapter contract stub for Qwen3.5-9B.

    In v1 we keep this deterministic and schema-strict so the rest of the stack is
    fully testable before swapping in actual local inference.
    """

    def analyze(self, packet: FeaturePacket) -> DecisionOutput:
        trend = packet.scores.trend_score
        mr = packet.scores.mean_reversion_score
        liq = packet.scores.liquidity_score

        if liq < 0.2:
            return DecisionOutput(
                side=TradeSide.NO_TRADE,
                confidence=0.4,
                thesis="Liquidity too low to justify a futures entry.",
                risks=["slippage_risk"],
                invalidation="volume_1m_usd >= target threshold",
                evidence_refs=[EvidenceRef(key="liquidity_score", value=liq)],
                requested_notional_usd=0.0,
            )

        score = 0.7 * trend + 0.3 * mr
        if score > 0.15:
            side = TradeSide.LONG
        elif score < -0.15:
            side = TradeSide.SHORT
        else:
            side = TradeSide.NO_TRADE

        conf = min(0.95, max(0.51, abs(score))) if side != TradeSide.NO_TRADE else 0.52
        requested = min(250.0, 40.0 + 300.0 * conf) if side != TradeSide.NO_TRADE else 0.0

        return DecisionOutput(
            side=side,
            confidence=conf,
            thesis="Trend/mean-reversion blended signal over deterministic packet.",
            risks=["funding_flip", "microstructure_noise"],
            invalidation="trend_score changes sign or zscore_20 crosses 0",
            evidence_refs=[
                EvidenceRef(key="trend_score", value=trend),
                EvidenceRef(key="mean_reversion_score", value=mr),
                EvidenceRef(key="liquidity_score", value=liq),
            ],
            requested_notional_usd=requested,
        )
