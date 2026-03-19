from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import Any
from pathlib import Path
import json
import random

import httpx


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace('Z', '+00:00'))


def round2(x: float) -> float:
    return round(float(x), 2)


def bucket_price(value: float, bucket_pct: float = 0.20) -> float:
    """Bucket by percentage to avoid tiny-noise ID churn while allowing material setup changes."""
    if value <= 0:
        return 0.0
    step = max(value * (bucket_pct / 100.0), 0.5)
    return round2(round(value / step) * step)


def blank_metrics() -> dict[str, Any]:
    return {
        'total_opened': 0,
        'total_closed': 0,
        'open_positions': 0,
        'tp_closes': 0,
        'sl_closes': 0,
        'time_exit_stale_closes': 0,
        'gross_realized_pnl': 0.0,
        'net_realized_pnl': 0.0,
        'gross_unrealized_pnl': 0.0,
        'net_unrealized_pnl': 0.0,
        'total_fees': 0.0,
        'fee_drag_pct': 0.0,
        'expectancy_net': 0.0,
        'median_time_to_close_min': 0,
        'avg_tp_progress_at_stale_close': 0.0,
        'risk_guard_blocks': 0,
        'duplicate_signal_skips': 0,
        'sample_closed': 0,
    }


STALE_EXIT_MIN_BARS = 8
STALE_EXIT_MIN_TP_PROGRESS = 0.35
BAR_MINUTES = 15

BASE_DIR = Path(__file__).resolve().parent
STATE_DIR = BASE_DIR / "data"
HL_STATE_FILE = STATE_DIR / "hyperliquid_paper_state.json"

HL_ACTIVE_STRATEGY_KEY = 'hl_15m_trend_follow_momo_gate_v1'

HL_STRATEGY_REGISTRY = {
    'hl_15m_trend_follow': {
        'strategy_key': 'hl_15m_trend_follow',
        'label': 'HL 15m trend-follow (active)',
        'family': 'trend_follow',
        'status': 'active',
        'paper_only': True,
        'shadow_only': False,
        'allowed_regimes': ['trend', 'breakout'],
    },
    'hl_15m_trend_follow_momo_gate_v1': {
        'strategy_key': 'hl_15m_trend_follow_momo_gate_v1',
        'label': 'HL 15m trend-follow momo-gate v1 (experimental shadow)',
        'family': 'trend_follow',
        'status': 'experimental_shadow',
        'paper_only': True,
        'shadow_only': True,
        'allowed_regimes': ['trend', 'breakout'],
        'momentum_gate_min_atr_body': 0.18,
    },
    'hl_15m_trend_follow_conflev_v1': {
        'strategy_key': 'hl_15m_trend_follow_conflev_v1',
        'label': 'HL 15m trend-follow conf-lev v1 (experimental shadow)',
        'family': 'trend_follow',
        'status': 'experimental_shadow',
        'paper_only': True,
        'shadow_only': True,
        'allowed_regimes': ['trend', 'breakout'],
    },
    'hl_15m_breakout_retest': {
        'strategy_key': 'hl_15m_breakout_retest',
        'label': 'HL 15m breakout-retest (planned shadow)',
        'family': 'breakout_retest',
        'status': 'planned_shadow',
        'paper_only': True,
        'shadow_only': True,
        'allowed_regimes': ['breakout', 'trend'],
    },
}


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
    strategy_key: str
    strategy_family: str
    market_regime: str
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
    high_conf_5x_used: bool = False
    leverage_stepup_reason: str = ''
    leverage_regime_confidence: float = 0.0
    leverage_entry_body_atr_ratio: float = 0.0
    leverage_spread_pct: float = 0.0


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

    def __init__(self, state_file: Path | None = None):
        self.risk = FuturesRiskLimits()
        self.fees = FuturesFeeModel()
        self.feed = HyperliquidPublicFeed(symbol='ETH')
        self.fallback_feed = MockPublicFeed()
        self.state_file = state_file or HL_STATE_FILE
        self.state: dict[str, Any] = {
            'track': 'hyperliquid_futures_paper',
            'paper_only': True,
            'live_trading_enabled': False,
            'private_execution_enabled': False,
            'exchange_execution_routes': [],
            'symbol': 'ETH-PERP',
            'active_strategy_key': HL_ACTIVE_STRATEGY_KEY,
            'strategy_registry': HL_STRATEGY_REGISTRY,
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
            'metrics': {
                'strategy_overall': {'hl_15m_trend_follow': blank_metrics()},
                'strategy_regime': {},
                'strategy_symbol': {'hl_15m_trend_follow|ETH-PERP': blank_metrics()},
            },
            'learning': {
                'notes': 'Mock/public-style futures simulator track initialized.',
                'status': 'training_bootstrap',
            },
        }
        self._load_state()
        self._reconcile_registry_and_metrics()

    def _persist_state(self) -> None:
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            snapshot = {
                'track': self.state.get('track'),
                'symbol': self.state.get('symbol'),
                'active_strategy_key': self.state.get('active_strategy_key'),
                'strategy_registry': self.state.get('strategy_registry'),
                'leverage_default': self.state.get('leverage_default'),
                'positions': self.state.get('positions', [])[-300:],
                'closed_trades': self.state.get('closed_trades', [])[-1000:],
                'history': self.state.get('history', [])[-1000:],
                'latest': self.state.get('latest'),
                'executed_signal_ids': self.state.get('executed_signal_ids', [])[-1000:],
                'risk_limits': self.state.get('risk_limits'),
                'fee_model': self.state.get('fee_model'),
                'execution_fee_assumption': self.state.get('execution_fee_assumption'),
                'metrics': self.state.get('metrics'),
                'learning': self.state.get('learning'),
            }
            tmp = self.state_file.with_suffix('.tmp')
            tmp.write_text(json.dumps(snapshot, separators=(',', ':')), encoding='utf-8')
            tmp.replace(self.state_file)
        except Exception:
            pass

    def _load_state(self) -> None:
        if not self.state_file.exists():
            return
        try:
            data = json.loads(self.state_file.read_text(encoding='utf-8'))
        except Exception:
            return

        for key in (
            'track', 'symbol', 'active_strategy_key', 'leverage_default',
            'positions', 'closed_trades', 'history', 'latest', 'executed_signal_ids',
            'risk_limits', 'fee_model', 'execution_fee_assumption', 'metrics', 'learning'
        ):
            if key in data:
                self.state[key] = data[key]

        # Merge saved registry into code registry instead of replacing it,
        # so newly added strategies remain visible after restart.
        saved_registry = data.get('strategy_registry') if isinstance(data, dict) else None
        merged_registry = dict(HL_STRATEGY_REGISTRY)
        if isinstance(saved_registry, dict):
            for k, v in saved_registry.items():
                if isinstance(v, dict):
                    merged_registry[k] = {**merged_registry.get(k, {}), **v}
        self.state['strategy_registry'] = merged_registry

    def _reconcile_registry_and_metrics(self) -> None:
        registry = self.state.get('strategy_registry') or {}
        if not isinstance(registry, dict):
            registry = {}
        # Ensure code-defined strategies always exist.
        for sk, sv in HL_STRATEGY_REGISTRY.items():
            if sk not in registry or not isinstance(registry.get(sk), dict):
                registry[sk] = dict(sv)
            else:
                merged = dict(sv)
                merged.update(registry[sk])
                registry[sk] = merged
        self.state['strategy_registry'] = registry

        # Route execution to requested active strategy key.
        active = self.state.get('active_strategy_key')
        if HL_ACTIVE_STRATEGY_KEY in registry:
            self.state['active_strategy_key'] = HL_ACTIVE_STRATEGY_KEY
        elif active not in registry:
            self.state['active_strategy_key'] = 'hl_15m_trend_follow'

        # Ensure per-strategy metric buckets exist for visibility/comparison.
        metrics = self.state.get('metrics') if isinstance(self.state.get('metrics'), dict) else {}
        overall = metrics.get('strategy_overall') if isinstance(metrics.get('strategy_overall'), dict) else {}
        symbol = self.state.get('symbol', 'ETH-PERP')
        by_symbol = metrics.get('strategy_symbol') if isinstance(metrics.get('strategy_symbol'), dict) else {}
        for sk in registry.keys():
            overall.setdefault(sk, blank_metrics())
            by_symbol.setdefault(f"{sk}|{symbol}", blank_metrics())
        metrics['strategy_overall'] = overall
        metrics['strategy_symbol'] = by_symbol
        if not isinstance(metrics.get('strategy_regime'), dict):
            metrics['strategy_regime'] = {}
        self.state['metrics'] = metrics

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

    def _atr(self, candles: list[dict[str, Any]], period: int = 14) -> float:
        if len(candles) < period + 1:
            return 0.0
        trs = []
        for i in range(-period, 0):
            c = candles[i]
            prev_close = candles[i - 1]['close']
            h = float(c['high'])
            l = float(c['low'])
            tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
            trs.append(tr)
        return round2(sum(trs) / len(trs)) if trs else 0.0

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
        atr = self._atr(candles, period=14)
        entry_candle = candles[-1]
        entry_body_atr_ratio = 0.0
        if atr > 0:
            if side == 'BUY':
                entry_body_atr_ratio = (float(entry_candle['close']) - float(entry_candle['open'])) / atr
            else:
                entry_body_atr_ratio = (float(entry_candle['open']) - float(entry_candle['close'])) / atr
        e_fp = bucket_price(entry, 0.20)
        s_fp = bucket_price(stop, 0.20)
        t_fp = bucket_price(tp, 0.20)
        signal_id = f"{self.state['track']}|{candles[-1].get('time')}|{side}|e:{e_fp}|s:{s_fp}|t:{t_fp}"
        return {
            'status': 'PROPOSE_TRADE',
            'strategy_key': self.state.get('active_strategy_key', 'hl_15m_trend_follow'),
            'strategy_family': (self.state.get('strategy_registry', {}).get(self.state.get('active_strategy_key', 'hl_15m_trend_follow'), {}) or {}).get('family', 'trend_follow'),
            'market_regime': regime.get('regime'),
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
            'entry_body_atr_ratio': round2(entry_body_atr_ratio),
            'atr': round2(atr),
            'spread_pct': round2(float(tick.get('spread_pct', 0))),
            'regime_confidence': round2(float(regime.get('confidence', 0))),
            'reason': f"Controlled futures proposal from {regime.get('regime')} regime.",
        }

    def _open_from_proposal(self, proposal: dict[str, Any], tick: dict[str, Any]) -> dict[str, Any]:
        side = proposal['side']
        qty = float(proposal['qty'])
        strategy_key = proposal.get('strategy_key', self.state.get('active_strategy_key', 'hl_15m_trend_follow'))
        base_lev = min(max(1.0, float(self.state['leverage_default'])), self.risk.max_leverage)
        high_conf_5x = False
        stepup_block_reason = 'not_conflev_variant'
        if strategy_key == 'hl_15m_trend_follow_conflev_v1':
            rg = str(proposal.get('market_regime') or '')
            rg_conf = float(proposal.get('regime_confidence') or 0.0)
            body_atr = float(proposal.get('entry_body_atr_ratio') or 0.0)
            spread_pct = float(proposal.get('spread_pct') or 0.0)
            if rg not in {'trend', 'breakout'}:
                stepup_block_reason = 'regime_not_trend_or_breakout'
            elif rg_conf < 0.85:
                stepup_block_reason = 'regime_confidence_below_0.85'
            elif body_atr < 0.30:
                stepup_block_reason = 'entry_body_atr_ratio_below_0.30'
            elif spread_pct > 0.02:
                stepup_block_reason = 'spread_pct_above_0.02'
            else:
                high_conf_5x = True
                stepup_block_reason = 'passed_all_gates'
        lev_target = 5.0 if high_conf_5x else base_lev
        lev_cap = 5.0 if strategy_key == 'hl_15m_trend_follow_conflev_v1' else self.risk.max_leverage
        lev = min(max(1.0, float(lev_target)), lev_cap)
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
            strategy_key=strategy_key,
            strategy_family=proposal.get('strategy_family', 'trend_follow'),
            market_regime=proposal.get('market_regime', 'unknown'),
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
            high_conf_5x_used=high_conf_5x,
            leverage_stepup_reason=stepup_block_reason,
            leverage_regime_confidence=round2(float(proposal.get('regime_confidence', 0.0))),
            leverage_entry_body_atr_ratio=round2(float(proposal.get('entry_body_atr_ratio', 0.0))),
            leverage_spread_pct=round2(float(proposal.get('spread_pct', 0.0))),
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

            close_reason = None
            exit_price = None
            if tp_hit or sl_hit:
                close_reason = 'TAKE_PROFIT' if tp_hit else 'STOP_LOSS'
                exit_price = p['take_profit'] if tp_hit else p['stop_loss']
            else:
                # Controlled stale exit: close only when BOTH conditions are met.
                # 1) bars_open >= STALE_EXIT_MIN_BARS
                # 2) tp_progress < STALE_EXIT_MIN_TP_PROGRESS (MFE-based)
                opened_at = parse_iso(p['open_time'])
                bars_open = int(((datetime.now(timezone.utc) - opened_at).total_seconds()) // (BAR_MINUTES * 60))
                tp_distance = abs(float(p['take_profit']) - entry) * qty
                tp_progress = (float(p.get('max_favorable_excursion', 0)) / tp_distance) if tp_distance > 0 else 0.0
                if bars_open >= STALE_EXIT_MIN_BARS and tp_progress < STALE_EXIT_MIN_TP_PROGRESS:
                    close_reason = 'TIME_EXIT_STALE'
                    exit_price = tick['bid'] if side == 'BUY' else tick['ask']

            if close_reason is not None and exit_price is not None:
                gross_realized = (exit_price - entry) * qty if side == 'BUY' else (entry - exit_price) * qty
                notional_exit = exit_price * qty
                exit_fee = round2(notional_exit * (self._fee_bps(p.get('exit_liquidity', 'taker')) / 10000.0))
                total_fees = round2(float(p.get('estimated_entry_fee', 0)) + exit_fee)
                net_realized = round2(gross_realized - total_fees)
                opened_at = parse_iso(p['open_time'])
                minutes_open = int((datetime.now(timezone.utc) - opened_at).total_seconds() // 60)
                tp_distance = abs(float(p['take_profit']) - entry) * qty
                tp_progress = (float(p.get('max_favorable_excursion', 0)) / tp_distance) if tp_distance > 0 else 0.0
                closed_trade = {
                    **p,
                    'status': 'PAPER_CLOSED',
                    'close_time': now_iso(),
                    'close_reason': close_reason,
                    'close_price': round2(exit_price),
                    'gross_realized_pnl': round2(gross_realized),
                    'net_realized_pnl': net_realized,
                    'realized_pnl': net_realized,
                    'estimated_exit_fee': exit_fee,
                    'estimated_total_fees': total_fees,
                    'bars_open_at_close': int(minutes_open // BAR_MINUTES),
                    'minutes_open_at_close': minutes_open,
                    'tp_progress_at_close': round2(tp_progress),
                }
                closed.append(closed_trade)
            else:
                still.append(p)
        self.state['positions'] = still
        if closed:
            self.state['closed_trades'].extend(closed)
            self.state['closed_trades'] = self.state['closed_trades'][-300:]
        return closed

    def _recompute_metrics(self) -> None:
        strategy_key = self.state.get('active_strategy_key', 'hl_15m_trend_follow')
        symbol = self.state.get('symbol', 'ETH-PERP')
        overall = blank_metrics()
        by_regime: dict[str, Any] = {}
        by_symbol = {f"{strategy_key}|{symbol}": blank_metrics()}

        closed = self.state.get('closed_trades', [])
        openp = self.state.get('positions', [])
        hist = self.state.get('history', [])

        overall['total_closed'] = len(closed)
        overall['open_positions'] = len(openp)
        overall['total_opened'] = len(closed) + len(openp)
        overall['gross_realized_pnl'] = round2(sum(float(t.get('gross_realized_pnl', 0)) for t in closed))
        overall['net_realized_pnl'] = round2(sum(float(t.get('net_realized_pnl', t.get('realized_pnl', 0))) for t in closed))
        overall['gross_unrealized_pnl'] = round2(sum(float(p.get('unrealized_pnl_gross', 0)) for p in openp))
        overall['net_unrealized_pnl'] = round2(sum(float(p.get('unrealized_pnl_net', 0)) for p in openp))
        overall['total_fees'] = round2(sum(float(t.get('estimated_total_fees', 0)) for t in closed) + sum(float(p.get('estimated_total_fees', 0)) for p in openp))
        overall['sample_closed'] = len(closed)
        overall['expectancy_net'] = round2(overall['net_realized_pnl'] / len(closed)) if closed else 0.0
        gross_total = overall['gross_realized_pnl'] + overall['gross_unrealized_pnl']
        overall['fee_drag_pct'] = round2((overall['total_fees'] / abs(gross_total)) * 100) if gross_total else 0.0
        overall['tp_closes'] = sum(1 for t in closed if t.get('close_reason') == 'TAKE_PROFIT')
        overall['sl_closes'] = sum(1 for t in closed if t.get('close_reason') == 'STOP_LOSS')
        overall['time_exit_stale_closes'] = sum(1 for t in closed if t.get('close_reason') == 'TIME_EXIT_STALE')
        overall['risk_guard_blocks'] = sum(1 for h in hist[-300:] if 'risk guard blocked open' in str((h.get('decision', {}) or {}).get('reason', '')).lower())
        overall['duplicate_signal_skips'] = sum(1 for h in hist[-300:] if 'duplicate signal skipped' in str((h.get('decision', {}) or {}).get('reason', '')).lower())
        mins = sorted(int(t.get('minutes_open_at_close', 0)) for t in closed if t.get('minutes_open_at_close') is not None)
        overall['median_time_to_close_min'] = (mins[len(mins)//2] if mins else 0)
        stale_prog = [float(t.get('tp_progress_at_close', 0)) for t in closed if t.get('close_reason') == 'TIME_EXIT_STALE']
        overall['avg_tp_progress_at_stale_close'] = round2(sum(stale_prog)/len(stale_prog)) if stale_prog else 0.0

        # strategy x regime buckets (future-proof for additional strategies later)
        regimes = ['trend', 'breakout', 'chop', 'low_edge']
        for rg in regimes:
            k = f"{strategy_key}|{rg}"
            by_regime[k] = blank_metrics()
            rg_closed = [t for t in closed if t.get('market_regime') == rg]
            rg_open = [p for p in openp if p.get('market_regime') == rg]
            by_regime[k]['total_closed'] = len(rg_closed)
            by_regime[k]['open_positions'] = len(rg_open)
            by_regime[k]['total_opened'] = len(rg_closed) + len(rg_open)
            by_regime[k]['gross_realized_pnl'] = round2(sum(float(t.get('gross_realized_pnl', 0)) for t in rg_closed))
            by_regime[k]['net_realized_pnl'] = round2(sum(float(t.get('net_realized_pnl', t.get('realized_pnl', 0))) for t in rg_closed))
            by_regime[k]['total_fees'] = round2(sum(float(t.get('estimated_total_fees', 0)) for t in rg_closed) + sum(float(p.get('estimated_total_fees', 0)) for p in rg_open))
            by_regime[k]['tp_closes'] = sum(1 for t in rg_closed if t.get('close_reason') == 'TAKE_PROFIT')
            by_regime[k]['sl_closes'] = sum(1 for t in rg_closed if t.get('close_reason') == 'STOP_LOSS')
            by_regime[k]['time_exit_stale_closes'] = sum(1 for t in rg_closed if t.get('close_reason') == 'TIME_EXIT_STALE')
            by_regime[k]['sample_closed'] = len(rg_closed)
            by_regime[k]['expectancy_net'] = round2(by_regime[k]['net_realized_pnl'] / len(rg_closed)) if rg_closed else 0.0

        by_symbol_key = f"{strategy_key}|{symbol}"
        by_symbol[by_symbol_key] = {**overall}

        prior_metrics = self.state.get('metrics') if isinstance(self.state.get('metrics'), dict) else {}
        strategy_overall = prior_metrics.get('strategy_overall') if isinstance(prior_metrics.get('strategy_overall'), dict) else {}
        strategy_symbol = prior_metrics.get('strategy_symbol') if isinstance(prior_metrics.get('strategy_symbol'), dict) else {}
        strategy_overall[strategy_key] = overall
        strategy_symbol.update(by_symbol)
        # Ensure visibility buckets exist for registered strategies, even if inactive.
        for sk in (self.state.get('strategy_registry') or {}).keys():
            strategy_overall.setdefault(sk, blank_metrics())
            strategy_symbol.setdefault(f"{sk}|{symbol}", blank_metrics())

        self.state['metrics'] = {
            'strategy_overall': strategy_overall,
            'strategy_regime': by_regime,
            'strategy_symbol': strategy_symbol,
        }

    def run_scan(self) -> dict[str, Any]:
        self._reconcile_registry_and_metrics()
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
            active_key = self.state.get('active_strategy_key', 'hl_15m_trend_follow')
            if active_key == 'hl_15m_trend_follow_momo_gate_v1':
                cfg = (self.state.get('strategy_registry', {}) or {}).get(active_key, {})
                min_body_atr = float(cfg.get('momentum_gate_min_atr_body', 0.18))
                atr = self._atr(candles, period=14)
                entry_candle = candles[-1] if candles else None
                body_ratio = 0.0
                if entry_candle and atr > 0:
                    o = float(entry_candle.get('open', 0))
                    c = float(entry_candle.get('close', 0))
                    if proposal.get('side') == 'BUY':
                        body_ratio = (c - o) / atr
                    else:
                        body_ratio = (o - c) / atr
                if not entry_candle or atr <= 0 or body_ratio < min_body_atr:
                    decision = {
                        'status': 'WAIT',
                        'reason': 'Entry blocked by momentum confirmation gate.',
                        'reason_code': 'entry_filter_momentum_fail',
                        'diagnostics': {
                            'momentum_gate_min_atr_body': round2(min_body_atr),
                            'entry_body_atr_ratio': round2(body_ratio),
                            'atr': round2(atr),
                            'entry_candle_open': round2(float(entry_candle.get('open', 0))) if entry_candle else 0.0,
                            'entry_candle_close': round2(float(entry_candle.get('close', 0))) if entry_candle else 0.0,
                        },
                    }
                else:
                    decision = proposal

            if decision.get('status') == 'PROPOSE_TRADE':
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
                'reason': f"Closed {len(closed_now)} paper position(s) by TP/SL/STALE.",
                'closed': closed_now[-3:],
            }

        self._recompute_metrics()

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
            'active_strategy_key': self.state.get('active_strategy_key'),
            'active_strategy_entry': (self.state.get('strategy_registry', {}) or {}).get(self.state.get('active_strategy_key', 'hl_15m_trend_follow')),
            'risk_limits': self.state['risk_limits'],
            'fee_model': self.state['fee_model'],
            'execution_fee_assumption': self.state.get('execution_fee_assumption', {}),
            'metrics': self.state.get('metrics', {}),
            'positions_open': len(self.state['positions']),
            'positions': self.state['positions'][-20:],
            'closed_trades': self.state['closed_trades'][-20:],
            'max_positions': self.risk.max_positions,
        }
        self.state['latest'] = latest
        self.state['history'].append(latest)
        self.state['history'] = self.state['history'][-300:]
        self._persist_state()
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
            strategy_key=self.state.get('active_strategy_key', 'hl_15m_trend_follow'),
            strategy_family=(self.state.get('strategy_registry', {}).get(self.state.get('active_strategy_key', 'hl_15m_trend_follow'), {}) or {}).get('family', 'trend_follow'),
            market_regime=((self.state.get('latest') or {}).get('regime') or {}).get('regime', 'manual'),
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
        self._recompute_metrics()
        self._persist_state()
        return {'ok': True, 'position': asdict(p)}

    def get_state(self) -> dict[str, Any]:
        return {
            **self.state,
            'positions': self.state['positions'][-30:],
            'closed_trades': self.state['closed_trades'][-100:],
            'history': self.state['history'][-100:],
        }
