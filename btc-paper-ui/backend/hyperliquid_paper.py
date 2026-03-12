from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
import random


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def round2(x: float) -> float:
    return round(float(x), 2)


@dataclass
class FuturesRiskLimits:
    max_leverage: float = 3.0
    max_total_exposure_usd: float = 300.0
    max_position_notional_usd: float = 150.0
    max_positions: int = 2
    max_risk_per_position_pct: float = 1.0


@dataclass
class FuturesFeeModel:
    maker_bps: float = 2.0
    taker_bps: float = 4.5
    funding_rate_placeholder_bps_8h: float = 0.0


@dataclass
class FuturesPosition:
    symbol: str
    side: str
    qty: float
    entry_price: float
    leverage: float
    margin_used: float
    liquidation_price_estimate: float
    open_time: str
    fee_model: str = 'maker_taker_bps'
    estimated_entry_fee: float = 0.0
    estimated_exit_fee: float = 0.0
    estimated_total_fees: float = 0.0
    unrealized_pnl_gross: float = 0.0
    unrealized_pnl_net: float = 0.0


class MockPublicFeed:
    """Public-style mock feed (no private execution paths)."""

    def __init__(self, seed: int = 42, start_price: float = 3200.0):
        self.rng = random.Random(seed)
        self.last_price = start_price

    def next_tick(self) -> dict[str, float]:
        drift = self.rng.uniform(-8.0, 8.0)
        self.last_price = max(10.0, self.last_price + drift)
        spread = max(0.2, abs(self.rng.uniform(0.2, 1.8)))
        bid = self.last_price - spread / 2
        ask = self.last_price + spread / 2
        return {
            'last': round2(self.last_price),
            'bid': round2(bid),
            'ask': round2(ask),
            'spread': round2(ask - bid),
            'spread_pct': round2(((ask - bid) / max((ask + bid) / 2, 1)) * 100),
        }


class HyperliquidFuturesPaperTrack:
    """
    Separate futures-oriented paper training track.
    - Paper-only
    - No private execution
    - No live deployment path
    """

    def __init__(self):
        self.risk = FuturesRiskLimits()
        self.fees = FuturesFeeModel()
        self.feed = MockPublicFeed()
        self.state: dict[str, Any] = {
            'track': 'hyperliquid_futures_paper',
            'paper_only': True,
            'live_trading_enabled': False,
            'private_execution_enabled': False,
            'exchange_execution_routes': [],
            'symbol': 'ETH-PERP',
            'leverage_default': 2.0,
            'positions': [],
            'history': [],
            'latest': None,
            'risk_limits': asdict(self.risk),
            'fee_model': asdict(self.fees),
            'learning': {
                'notes': 'Mock/public-style futures simulator track initialized.',
                'status': 'training_bootstrap',
            },
        }

    def _estimate_liq_price(self, side: str, entry: float, leverage: float) -> float:
        # Conservative rough estimate for paper training only.
        if leverage <= 0:
            leverage = 1.0
        move = entry / max(leverage, 1.0)
        if side == 'BUY':
            return round2(max(1.0, entry - move))
        return round2(entry + move)

    def _estimate_fees(self, notional: float) -> tuple[float, float, float]:
        entry_fee = notional * (self.fees.taker_bps / 10000.0)
        exit_fee = notional * (self.fees.taker_bps / 10000.0)
        return round2(entry_fee), round2(exit_fee), round2(entry_fee + exit_fee)

    def _regime_from_tick(self, tick: dict[str, float]) -> dict[str, Any]:
        sp = tick['spread_pct']
        if sp > 0.03:
            regime = 'low_edge'
            confidence = 0.82
            reason = 'Spread too wide for efficient paper futures execution.'
        elif abs(tick['last'] - self.feed.last_price) > 6:
            regime = 'breakout'
            confidence = 0.7
            reason = 'Large synthetic tick displacement.'
        else:
            regime = 'chop'
            confidence = 0.6
            reason = 'Synthetic price action in compressed range.'
        return {
            'regime': regime,
            'confidence': confidence,
            'reason': reason,
        }

    def run_scan(self) -> dict[str, Any]:
        tick = self.feed.next_tick()
        regime = self._regime_from_tick(tick)
        latest = {
            'timestamp': now_iso(),
            'track': self.state['track'],
            'paper_only': True,
            'symbol': self.state['symbol'],
            'market': tick,
            'regime': regime,
            'decision': {
                'status': 'WAIT',
                'reason': 'Phase 3 simulator active (mock/public-only). No auto execution enabled.',
            },
            'risk_limits': self.state['risk_limits'],
            'fee_model': self.state['fee_model'],
            'positions_open': len(self.state['positions']),
            'max_positions': self.risk.max_positions,
        }
        self.state['latest'] = latest
        self.state['history'].append(latest)
        self.state['history'] = self.state['history'][-300:]
        return latest

    def open_paper_position(self, side: str, qty: float, leverage: float | None = None) -> dict[str, Any]:
        """Explicit paper-only helper (not auto-routed, no exchange calls)."""
        if len(self.state['positions']) >= self.risk.max_positions:
            return {'ok': False, 'reason': 'max positions reached'}

        tick = self.feed.next_tick()
        px = tick['ask'] if side == 'BUY' else tick['bid']
        lev = float(leverage or self.state['leverage_default'])
        lev = min(max(1.0, lev), self.risk.max_leverage)
        notional = px * qty
        if notional > self.risk.max_position_notional_usd:
            return {'ok': False, 'reason': 'position notional exceeds per-position cap'}
        exposure = sum(p['entry_price'] * p['qty'] for p in self.state['positions'])
        if exposure + notional > self.risk.max_total_exposure_usd:
            return {'ok': False, 'reason': 'total exposure cap exceeded'}

        margin_used = notional / lev
        liq = self._estimate_liq_price(side, px, lev)
        efee, xfee, tfee = self._estimate_fees(notional)

        p = FuturesPosition(
            symbol=self.state['symbol'],
            side=side,
            qty=qty,
            entry_price=px,
            leverage=lev,
            margin_used=round2(margin_used),
            liquidation_price_estimate=liq,
            open_time=now_iso(),
            estimated_entry_fee=efee,
            estimated_exit_fee=xfee,
            estimated_total_fees=tfee,
        )
        self.state['positions'].append(asdict(p))
        return {'ok': True, 'position': asdict(p)}

    def get_state(self) -> dict[str, Any]:
        return {
            **self.state,
            'positions': self.state['positions'][-30:],
            'history': self.state['history'][-100:],
        }
