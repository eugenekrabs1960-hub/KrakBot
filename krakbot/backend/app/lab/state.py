from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.lab.contracts import AccountSnapshot, MarketSnapshot, ModeState


@dataclass
class RuntimeState:
    mode: ModeState = field(default_factory=ModeState)
    price_history: list[float] = field(default_factory=lambda: [42000.0] * 30)
    logs: list[dict] = field(default_factory=list)
    paper_positions: dict[str, float] = field(default_factory=dict)


STATE = RuntimeState()


def get_market_snapshot(symbol: str = "BTC") -> MarketSnapshot:
    last = STATE.price_history[-1]
    shock = random.uniform(-0.002, 0.002)
    next_price = max(100.0, last * (1 + shock))
    STATE.price_history.append(next_price)
    STATE.price_history[:] = STATE.price_history[-100:]
    spread_bps = max(1.0, min(20.0, random.uniform(2.0, 10.0)))
    volume_1m = random.uniform(900_000, 4_500_000)
    return MarketSnapshot(
        symbol=symbol,
        mid_price=next_price,
        mark_price=next_price,
        spread_bps=spread_bps,
        funding_rate_8h=random.uniform(-0.0005, 0.0005),
        volume_1m_usd=volume_1m,
        timestamp=datetime.now(timezone.utc),
    )


def get_account_snapshot() -> AccountSnapshot:
    open_positions = sum(1 for qty in STATE.paper_positions.values() if abs(qty) > 0)
    return AccountSnapshot(
        equity_usd=10_000,
        free_collateral_usd=8_500,
        open_positions=open_positions,
        daily_pnl_pct=random.uniform(-1.0, 1.0),
    )
