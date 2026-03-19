from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.lab.analyst import LocalQwenAnalystAdapter
from app.lab.brokers import LiveHyperliquidBroker, PaperBroker
from app.lab.contracts import (
    CycleLog,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    FeaturePacket,
)
from app.lab.features import compute_features
from app.lab.policy import run_policy_gate
from app.lab.profiles import MODEL_PROFILES, RISK_PROFILES, SCORE_PROFILES
from app.lab.scoring import compute_scores
from app.lab.state import STATE, get_account_snapshot, get_market_snapshot


class TradingLabEngine:
    def __init__(self) -> None:
        self.analyst = LocalQwenAnalystAdapter()
        self.paper_broker = PaperBroker()
        self.live_broker = LiveHyperliquidBroker()

    def run_cycle(self, symbol: str = "BTC") -> CycleLog:
        mode = STATE.mode
        market = get_market_snapshot(symbol=symbol)
        account = get_account_snapshot()

        score_profile = SCORE_PROFILES[mode.score_profile_id]
        features = compute_features(spread_bps=market.spread_bps, volume_1m_usd=market.volume_1m_usd)
        scores = compute_scores(features, target_volume_1m_usd=score_profile["liquidity_target_volume_1m_usd"])

        packet = FeaturePacket(
            packet_id=f"pkt-{uuid.uuid4().hex[:12]}",
            symbol=symbol,
            created_at=datetime.now(timezone.utc),
            market=market,
            account=account,
            features=features,
            scores=scores,
            risk_profile_id=mode.risk_profile_id,
            model_profile_id=mode.model_profile_id,
        )

        decision = self.analyst.analyze(packet)
        risk_profile = RISK_PROFILES[mode.risk_profile_id]
        gate = run_policy_gate(packet, decision, risk_profile)

        execution: ExecutionResult | None = None
        if gate.allowed:
            req = ExecutionRequest(
                mode=mode.execution_mode,
                symbol=symbol,
                side="buy" if decision.side.value == "long" else "sell",
                notional_usd=min(decision.requested_notional_usd, gate.max_allowed_notional_usd),
            )
            if mode.execution_mode == ExecutionMode.PAPER:
                execution = self.paper_broker.execute(req, mark_price=market.mark_price)
            else:
                if not mode.live_armed:
                    execution = ExecutionResult(accepted=False, reason="live_mode_not_armed")
                else:
                    execution = self.live_broker.execute(req, mark_price=market.mark_price)

        cycle = CycleLog(
            cycle_id=f"cycle-{uuid.uuid4().hex[:10]}",
            packet=packet,
            decision=decision,
            gate=gate,
            execution=execution,
            labels={"outcome_label": "pending"},
        )
        STATE.logs.append(cycle.model_dump())
        STATE.logs[:] = STATE.logs[-500:]
        return cycle


ENGINE = TradingLabEngine()


def profiles_snapshot() -> dict:
    return {
        "risk": {k: v.__dict__ for k, v in RISK_PROFILES.items()},
        "model": MODEL_PROFILES,
        "score": SCORE_PROFILES,
    }
