from __future__ import annotations

import uuid
from typing import Protocol

from app.lab.contracts import ExecutionRequest, ExecutionResult
from app.lab.state import STATE


class Broker(Protocol):
    def execute(self, request: ExecutionRequest, mark_price: float) -> ExecutionResult: ...


class PaperBroker:
    def execute(self, request: ExecutionRequest, mark_price: float) -> ExecutionResult:
        signed_qty = request.notional_usd / max(mark_price, 1e-9)
        if request.side == "sell":
            signed_qty = -signed_qty
        STATE.paper_positions[request.symbol] = STATE.paper_positions.get(request.symbol, 0.0) + signed_qty
        return ExecutionResult(
            accepted=True,
            broker_order_id=f"paper-{uuid.uuid4().hex[:12]}",
            fill_price=mark_price,
            filled_notional_usd=request.notional_usd,
            details={"position_qty": STATE.paper_positions[request.symbol]},
        )


class LiveHyperliquidBroker:
    """Live adapter stub for initial skeleton.

    Intentional in v1: contract exists and routing works, real signing/transport can
    be wired into this class without changing orchestration.
    """

    def execute(self, request: ExecutionRequest, mark_price: float) -> ExecutionResult:
        return ExecutionResult(
            accepted=False,
            reason="live_hyperliquid_not_connected",
            details={"hint": "wire Hyperliquid API signer + transport in this adapter"},
        )
