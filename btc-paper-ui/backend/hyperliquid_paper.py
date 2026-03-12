from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import Any
import random

import httpx


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def round2(x: float) -> float:
    return round(float(x), 2)


def bucket_price(value: float, bucket_pct: float = 0.20) -> float:
    """Bucket by percentage to avoid tiny-noise ID churn while allowing material setup changes."""
    if value <= 0:
        return 0.0
    step = max(value * (bucket_pct / 100.0), 0.5)
    return round2(round(value / step) * step)


@dataclass
class FuturesRiskLimits:
    max_leverage: float = 3.0
    max_total_exposure_usd: float = 300.0
    max_position_notional_usd: float = 150.0
    max_positions: int = 2
    max_risk_per_position_pct: float = 1.0


@dataclass
class FuturesFeeModel:
    # Hyperliquid perps base-rate defaults (tier 0): maker 0.015%, taker 0.045%
    maker_bps: float = 1.5
    taker_bps: float = 4.5
    funding_rate_placeholder_bps_8h: float = 0.0
    funding_mode: str = 'placeholder_zero'
    fee_source: str = 'hyperliquid_perps_base_tier_0'


@dataclass
class FuturesPosition:
    symbol: str
    side: str
    qty: float
    entry_price: float
    leverage: float
    margin_used: float
    liquidation_price_estimate: float
    stop_loss: float
    take_profit: float
    signal_id: str
    open_time: str
    status: str = 'PAPER_OPEN'
    fee_model: str = 'maker_taker_bps'
    entry_liquidity: str = 'taker'
    exit_liquidity: str = 'taker'
    estimated_entry_fee: float = 0.0
    estimated_exit_fee: float = 0.0
    estimated_total_fees: float = 0.0
    unrealized_pnl_gross: float = 0.0
    unrealized_pnl_net: float = 0.0
    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0


class MockPublicFeed:
    """Fallback-only synthetic feed if public endpoints are temporarily unavailable."""

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
            'source': 'mock_fallback',
        }


class HyperliquidPublicFeed:
    """Read-only Hyperliquid public market feed (no signed/private routes)."""

    def __init__(self, symbol: str = 'ETH'):
        self.symbol = symbol
        self.url = 'https://api.hyperliquid.xyz/info'
        self.timeout = 15

    def _post(self, payload: dict[str, Any]) -> Any:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(self.url, json=payload)
            r.raise_for_status()
            return r.json()

    def fetch_tick(self) -> dict[str, Any]:
        mids = self._post({'type': 'allMids'})
        px = float(mids.get(self.symbol) or mids.get(f'{self.symbol}-PERP') or 0)
        if px <= 0:
            raise RuntimeError('No public mid price returned for symbol')
        # allMids is midpoint only; use a tight synthetic spread around real mid for simulator bookkeeping.
        spread = max(px * 0.00004, 0.2)
        bid = px - spread / 2
        ask = px + spread / 2
        return {
            'last': round2(px),
            'bid': round2(bid),
            'ask': round2(ask),
            'spread': round2(ask - bid),
            'spread_pct': round2(((ask - bid) / max((ask + bid) / 2, 1)) * 100),
            'source': 'hyperliquid_public_allMids',
        }

    def fetch_candles(self, interval: str = '15m', bars: int = 24) -> list[dict[str, Any]]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=15 * bars)
        payload = {
            'type': 'candleSnapshot',
            'req': {
                'coin': self.symbol,
                'interval': interval,
                'startTime': int(start.timestamp() * 1000),
                'endTime': int(end.timestamp() * 1000),
            },
        }
        rows = self._post(payload)
        candles = []
        for r in rows[-bars:]:
            candles.append({
                'time': r.get('t') or r.get('time'),
                'open': float(r.get('o', 0)),
                'high': float(r.get('h', 0)),
                'low': float(r.get('l', 0)),
                'close': float(r.get('c', 0)),
                'volume': float(r.get('v', 0)),
            })
        return candles


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
        self.feed = HyperliquidPublicFeed(symbol='ETH')
        self.fallback_feed = MockPublicFeed()
        self.state: dict[str, Any] = {
            'track': 'hyperliquid_futures_paper',
            'paper_only': True,
            'live_trading_enabled': False,
            'private_execution_enabled': False,
            'exchange_execution_routes': [],
            'symbol': 'ETH-PERP',
            'leverage_default': 2.0,
            'positions': [],
            'closed_trades': [],
            'history': [],
            'latest': None,
            'executed_signal_ids': [],
            'risk_limits': asdict(self.risk),
            'fee_model': asdict(self.fees),
            'execution_fee_assumption': {
                'entry_liquidity': 'taker',
                'exit_liquidity': 'taker',
                'note': 'Paper simulator assumes taker fills for conservative cost modeling.',
            },
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

    def _fee_bps(self, liquidity: str) -> float:
        return self.fees.maker_bps if liquidity == 'maker' else self.fees.taker_bps

    def _estimate_fees(self, notional: float, entry_liquidity: str = 'taker', exit_liquidity: str = 'taker') -> tuple[float, float, float]:
        entry_fee = notional * (self._fee_bps(entry_liquidity) / 10000.0)
        exit_fee = notional * (self._fee_bps(exit_liquidity) / 10000.0)
        return round2(entry_fee), round2(exit_fee), round2(entry_fee + exit_fee)

    def _regime_from_market(self, tick: dict[str, float], candles: list[dict[str, Any]]) -> dict[str, Any]:
        sp = tick['spread_pct']
        if sp > 0.03:
            return {
                'regime': 'low_edge',
                'confidence': 0.82,
                'reason': 'Spread too wide for efficient paper futures execution.',
            }

        closes = [c['close'] for c in candles if c.get('close')]
        highs = [c['high'] for c in candles if c.get('high')]
        lows = [c['low'] for c in candles if c.get('low')]
        if len(closes) < 6 or len(highs) < 6 or len(lows) < 6:
            return {
                'regime': 'low_edge',
                'confidence': 0.55,
                'reason': 'Insufficient public candle depth for robust regime classification.',
            }

        recent = closes[-6:]
        net_move = recent[-1] - recent[0]
        step = sum(abs(recent[i] - recent[i - 1]) for i in range(1, len(recent)))
        directionality = abs(net_move) / max(step, 0.1)
        six_high = max(highs[-6:])
        six_low = min(lows[-6:])
        six_range = max(six_high - six_low, 0.1)
        compression = six_range / max(recent[-1], 1)

        if recent[-1] > max(highs[-6:-1]) or recent[-1] < min(lows[-6:-1]):
            return {
                'regime': 'breakout',
                'confidence': round2(min(0.9, 0.62 + directionality * 0.2)),
                'reason': 'Public candle structure shows short-term breakout displacement.',
            }
        if directionality > 0.62 and compression > 0.004:
            return {
                'regime': 'trend',
                'confidence': round2(min(0.9, 0.56 + directionality * 0.25)),
                'reason': 'Public candle sequence shows directional follow-through.',
            }
        if compression <= 0.0045:
            return {
                'regime': 'chop',
                'confidence': 0.66,
                'reason': 'Public candle range is compressed/choppy.',
            }
        return {
            'regime': 'low_edge',
            'confidence': 0.58,
            'reason': 'Public market structure does not show clear edge.',
        }

    def _compute_qty(self, entry_price: float) -> float:
        cap_qty = self.risk.max_position_notional_usd / max(entry_price, 1.0)
        return round(max(0.001, min(0.03, cap_qty)), 4)

    def _build_proposal(self, tick: dict[str, Any], candles: list[dict[str, Any]], regime: dict[str, Any]) -> dict[str, Any]:
        if regime.get('regime') not in {'trend', 'breakout'}:
            return {'status': 'WAIT', 'reason': 'No futures entry: regime not actionable for controlled simulator.'}
        if len(candles) < 8:
            return {'status': 'WAIT', 'reason': 'No futures entry: insufficient candle depth.'}

        closes = [c['close'] for c in candles[-8:]]
        highs = [c['high'] for c in candles[-8:]]
        lows = [c['low'] for c in candles[-8:]]
        up = closes[-1] >= closes[0]
        side = 'BUY' if up else 'SELL'
        entry = tick['ask'] if side == 'BUY' else tick['bid']
        if side == 'BUY':
            stop = min(lows[-5:]) * 0.999
            risk = max(entry - stop, entry * 0.0025)
            stop = entry - risk
            tp = entry + risk * 1.8
        else:
            stop = max(highs[-5:]) * 1.001
            risk = max(stop - entry, entry * 0.0025)
            stop = entry + risk
            tp = entry - risk * 1.8
        qty = self._compute_qty(entry)
        e_fp = bucket_price(entry, 0.20)
        s_fp = bucket_price(stop, 0.20)
        t_fp = bucket_price(tp, 0.20)
        signal_id = f"{self.state['track']}|{candles[-1].get('time')}|{side}|e:{e_fp}|s:{s_fp}|t:{t_fp}"
        return {
            'status': 'PROPOSE_TRADE',
            'side': side,
            'entry_price': round2(entry),
            'stop_loss': round2(stop),
            'take_profit': round2(tp),
            'risk_reward_ratio': 1.8,
            'qty': qty,
            'signal_id': signal_id,
            'signal_fingerprint': {
                'entry_bucket': e_fp,
                'stop_bucket': s_fp,
                'tp_bucket': t_fp,
                'bucket_pct': 0.20,
            },
            'reason': f"Controlled futures proposal from {regime.get('regime')} regime.",
        }

    def _open_from_proposal(self, proposal: dict[str, Any], tick: dict[str, Any]) -> dict[str, Any]:
        side = proposal['side']
        qty = float(proposal['qty'])
        lev = min(max(1.0, float(self.state['leverage_default'])), self.risk.max_leverage)
        entry = float(proposal['entry_price'])
        notional = entry * qty
        if len(self.state['positions']) >= self.risk.max_positions:
            return {'ok': False, 'reason': 'max positions reached'}
        if notional > self.risk.max_position_notional_usd:
            return {'ok': False, 'reason': 'position notional exceeds per-position cap'}
        exposure = sum(p['entry_price'] * p['qty'] for p in self.state['positions'])
        if exposure + notional > self.risk.max_total_exposure_usd:
            return {'ok': False, 'reason': 'total exposure cap exceeded'}

        margin_used = notional / lev
        liq = self._estimate_liq_price(side, entry, lev)
        entry_liq = self.state.get('execution_fee_assumption', {}).get('entry_liquidity', 'taker')
        exit_liq = self.state.get('execution_fee_assumption', {}).get('exit_liquidity', 'taker')
        efee, xfee, tfee = self._estimate_fees(notional, entry_liq, exit_liq)
        p = FuturesPosition(
            symbol=self.state['symbol'],
            side=side,
            qty=qty,
            entry_price=entry,
            leverage=lev,
            margin_used=round2(margin_used),
            liquidation_price_estimate=liq,
            stop_loss=float(proposal['stop_loss']),
            take_profit=float(proposal['take_profit']),
            signal_id=proposal['signal_id'],
            open_time=now_iso(),
            entry_liquidity=entry_liq,
            exit_liquidity=exit_liq,
            estimated_entry_fee=efee,
            estimated_exit_fee=xfee,
            estimated_total_fees=tfee,
        )
        self.state['positions'].append(asdict(p))
        self.state['executed_signal_ids'].append(proposal['signal_id'])
        self.state['executed_signal_ids'] = self.state['executed_signal_ids'][-500:]
        return {'ok': True, 'position': asdict(p)}

    def _update_positions(self, tick: dict[str, Any]) -> list[dict[str, Any]]:
        closed = []
        still = []
        for p in self.state['positions']:
            side = p['side']
            qty = float(p['qty'])
            entry = float(p['entry_price'])
            mark = tick['bid'] if side == 'BUY' else tick['ask']
            gross = (mark - entry) * qty if side == 'BUY' else (entry - mark) * qty
            net = gross - float(p.get('estimated_total_fees', 0))
            p['unrealized_pnl_gross'] = round2(gross)
            p['unrealized_pnl_net'] = round2(net)
            p['max_favorable_excursion'] = round2(max(float(p.get('max_favorable_excursion', 0)), gross if gross > 0 else 0))
            p['max_adverse_excursion'] = round2(max(float(p.get('max_adverse_excursion', 0)), -gross if gross < 0 else 0))

            tp_hit = (side == 'BUY' and tick['bid'] >= p['take_profit']) or (side == 'SELL' and tick['ask'] <= p['take_profit'])
            sl_hit = (side == 'BUY' and tick['bid'] <= p['stop_loss']) or (side == 'SELL' and tick['ask'] >= p['stop_loss'])
            if tp_hit or sl_hit:
                exit_price = p['take_profit'] if tp_hit else p['stop_loss']
                gross_realized = (exit_price - entry) * qty if side == 'BUY' else (entry - exit_price) * qty
                notional_exit = exit_price * qty
                exit_fee = round2(notional_exit * (self._fee_bps(p.get('exit_liquidity', 'taker')) / 10000.0))
                total_fees = round2(float(p.get('estimated_entry_fee', 0)) + exit_fee)
                net_realized = round2(gross_realized - total_fees)
                closed_trade = {
                    **p,
                    'status': 'PAPER_CLOSED',
                    'close_time': now_iso(),
                    'close_reason': 'TAKE_PROFIT' if tp_hit else 'STOP_LOSS',
                    'close_price': round2(exit_price),
                    'gross_realized_pnl': round2(gross_realized),
                    'net_realized_pnl': net_realized,
                    'realized_pnl': net_realized,
                    'estimated_exit_fee': exit_fee,
                    'estimated_total_fees': total_fees,
                }
                closed.append(closed_trade)
            else:
                still.append(p)
        self.state['positions'] = still
        if closed:
            self.state['closed_trades'].extend(closed)
            self.state['closed_trades'] = self.state['closed_trades'][-300:]
        return closed

    def run_scan(self) -> dict[str, Any]:
        source = 'hyperliquid_public'
        candles: list[dict[str, Any]] = []
        try:
            tick = self.feed.fetch_tick()
            candles = self.feed.fetch_candles(interval='15m', bars=24)
        except Exception:
            source = 'mock_fallback'
            tick = self.fallback_feed.next_tick()
            candles = []

        regime = self._regime_from_market(tick, candles)
        closed_now = self._update_positions(tick)
        proposal = self._build_proposal(tick, candles, regime)
        decision = proposal

        if proposal.get('status') == 'PROPOSE_TRADE':
            if proposal['signal_id'] in set(self.state.get('executed_signal_ids', [])):
                decision = {'status': 'WAIT', 'reason': 'Duplicate signal skipped in paper simulator.'}
            else:
                opened = self._open_from_proposal(proposal, tick)
                if opened.get('ok'):
                    decision = {
                        'status': 'PAPER_TRADE_OPEN',
                        'reason': 'Controlled paper proposal auto-opened inside Hyperliquid paper track.',
                        'proposal': proposal,
                    }
                else:
                    decision = {'status': 'WAIT', 'reason': f"Paper risk guard blocked open: {opened.get('reason')}"}

        if closed_now:
            decision = {
                'status': 'PAPER_TRADE_CLOSED',
                'reason': f"Closed {len(closed_now)} paper position(s) by TP/SL.",
                'closed': closed_now[-3:],
            }

        latest = {
            'timestamp': now_iso(),
            'track': self.state['track'],
            'paper_only': True,
            'symbol': self.state['symbol'],
            'market_source': source,
            'market': tick,
            'candles': candles[-24:],
            'regime': regime,
            'decision': decision,
            'risk_limits': self.state['risk_limits'],
            'fee_model': self.state['fee_model'],
            'execution_fee_assumption': self.state.get('execution_fee_assumption', {}),
            'positions_open': len(self.state['positions']),
            'positions': self.state['positions'][-20:],
            'closed_trades': self.state['closed_trades'][-20:],
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

        try:
            tick = self.feed.fetch_tick()
        except Exception:
            tick = self.fallback_feed.next_tick()
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
        entry_liq = self.state.get('execution_fee_assumption', {}).get('entry_liquidity', 'taker')
        exit_liq = self.state.get('execution_fee_assumption', {}).get('exit_liquidity', 'taker')
        efee, xfee, tfee = self._estimate_fees(notional, entry_liq, exit_liq)

        risk = max(px * 0.0025, 1.0)
        stop = round2(px - risk) if side == 'BUY' else round2(px + risk)
        tp = round2(px + risk * 1.8) if side == 'BUY' else round2(px - risk * 1.8)
        p = FuturesPosition(
            symbol=self.state['symbol'],
            side=side,
            qty=qty,
            entry_price=px,
            leverage=lev,
            margin_used=round2(margin_used),
            liquidation_price_estimate=liq,
            stop_loss=stop,
            take_profit=tp,
            signal_id=f"manual|{now_iso()}|{side}",
            open_time=now_iso(),
            entry_liquidity=entry_liq,
            exit_liquidity=exit_liq,
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
            'closed_trades': self.state['closed_trades'][-100:],
            'history': self.state['history'][-100:],
        }
