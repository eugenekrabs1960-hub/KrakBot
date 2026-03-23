from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import Any
from pathlib import Path
import json
import random
import shutil

import httpx

NEWS_STATE_FILE = Path(__file__).resolve().parent / 'data' / 'news_context_state.json'


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


def blank_book() -> dict[str, Any]:
    return {
        'positions': [],
        'closed_trades': [],
        'history': [],
        'executed_signal_ids': [],
        'latest': None,
    }


STALE_EXIT_MIN_BARS = 8
STALE_EXIT_MIN_TP_PROGRESS = 0.35
BAR_MINUTES = 15

BASE_DIR = Path(__file__).resolve().parent
STATE_DIR = BASE_DIR / "data"
HL_STATE_FILE = STATE_DIR / "hyperliquid_paper_state.json"

# Persistence safety caps (disk-usage guardrails)
MAX_POSITIONS_PERSIST = 300
MAX_CLOSED_TRADES_PERSIST = 300
MAX_HISTORY_PERSIST = 300
MAX_SIGNAL_IDS_PERSIST = 500
MAX_LATEST_POSITIONS_VIEW = 10
MAX_LATEST_CLOSED_VIEW = 10

BACKUP_RETENTION_COUNT = 6
BACKUP_MIN_INTERVAL_SECONDS = 3600

HL_ACTIVE_STRATEGY_KEYS = [
    'hl_15m_trend_follow_momo_gate_v1',
]

HL_STRATEGY_REGISTRY = {
    'hl_15m_trend_follow': {
        'strategy_key': 'hl_15m_trend_follow',
        'label': 'Hyperliquid Reference (Shadow)',
        'family': 'trend_follow',
        'status': 'reference_shadow',
        'paper_only': True,
        'shadow_only': True,
        'allowed_regimes': ['trend', 'breakout'],
    },
    'hl_15m_trend_follow_momo_gate_v1': {
        'strategy_key': 'hl_15m_trend_follow_momo_gate_v1',
        'label': 'Hyperliquid Learner (Autonomous) · Momo Gate v1',
        'family': 'trend_follow',
        'status': 'active_learner',
        'paper_only': True,
        'shadow_only': False,
        'allowed_regimes': ['trend', 'breakout'],
        'momentum_gate_min_atr_body': 0.18,
        'max_leverage': 10.0,
        'leverage_target': 4.0,
        'max_positions': 2,
        'max_position_notional_usd': 150.0,
        'max_total_exposure_usd': 300.0,
    },
    'hl_15m_trend_follow_conflev_v1': {
        'strategy_key': 'hl_15m_trend_follow_conflev_v1',
        'label': 'Hyperliquid Secondary (Paused Shadow) · ConfLev v1',
        'family': 'trend_follow',
        'status': 'paused_shadow',
        'paper_only': True,
        'shadow_only': True,
        'allowed_regimes': ['trend', 'breakout'],
    },
    'hl_15m_breakout_retest': {
        'strategy_key': 'hl_15m_breakout_retest',
        'label': 'Hyperliquid Breakout (Paused Shadow)',
        'family': 'breakout_retest',
        'status': 'paused_shadow',
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
            'active_strategy_keys': list(HL_ACTIVE_STRATEGY_KEYS),
            'active_strategy_key': HL_ACTIVE_STRATEGY_KEYS[0],
            'strategy_registry': HL_STRATEGY_REGISTRY,
            'leverage_default': 2.0,
            'books': {k: blank_book() for k in HL_STRATEGY_REGISTRY.keys()},
            'positions': [],
            'closed_trades': [],
            'history': [],
            'latest': None,
            'latest_by_strategy': {},
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

    def _rotate_backups(self) -> None:
        try:
            pattern = f"{self.state_file.stem}.*.bak.json"
            backups = sorted(self.state_file.parent.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
            for stale in backups[BACKUP_RETENTION_COUNT:]:
                stale.unlink(missing_ok=True)
        except Exception:
            pass

    def _has_recent_backup(self, reason: str) -> bool:
        try:
            pattern = f"{self.state_file.stem}.{reason}.*.bak.json"
            backups = sorted(self.state_file.parent.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
            if not backups:
                return False
            newest = backups[0]
            age = datetime.now(timezone.utc).timestamp() - newest.stat().st_mtime
            return age < BACKUP_MIN_INTERVAL_SECONDS
        except Exception:
            return False

    def _backup_state_file(self, reason: str = 'pre-save', force: bool = False) -> None:
        try:
            if not self.state_file.exists():
                return
            if not force and self._has_recent_backup(reason):
                return
            ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            bak = self.state_file.with_name(f"{self.state_file.stem}.{reason}.{ts}.bak.json")
            if bak.exists():
                return
            shutil.copy2(self.state_file, bak)
            self._rotate_backups()
        except Exception:
            pass

    def _legacy_migration_needed(self, books: dict[str, Any] | None, data: dict[str, Any]) -> bool:
        legacy_positions = data.get('positions') or []
        legacy_closed = data.get('closed_trades') or []
        if not legacy_positions and not legacy_closed:
            return False
        if not isinstance(books, dict) or not books:
            return True
        book_pos = sum(len((b or {}).get('positions', []) or []) for b in books.values() if isinstance(b, dict))
        book_closed = sum(len((b or {}).get('closed_trades', []) or []) for b in books.values() if isinstance(b, dict))
        return (book_pos == 0 and len(legacy_positions) > 0) or (book_closed == 0 and len(legacy_closed) > 0)

    def _migrate_legacy_into_books(self, books: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        migrated = {k: (v if isinstance(v, dict) else blank_book()) for k, v in books.items()}
        for p in data.get('positions', []) or []:
            sk = p.get('strategy_key') or 'hl_15m_trend_follow'
            migrated.setdefault(sk, blank_book())['positions'].append(p)
        for t in data.get('closed_trades', []) or []:
            sk = t.get('strategy_key') or 'hl_15m_trend_follow'
            migrated.setdefault(sk, blank_book())['closed_trades'].append(t)
        base = migrated.setdefault('hl_15m_trend_follow', blank_book())
        if not base.get('history'):
            base['history'] = list(data.get('history', []) or [])[-MAX_HISTORY_PERSIST:]
        for sk, b in migrated.items():
            ids = list(b.get('executed_signal_ids', []) or [])
            if not ids:
                for p in b.get('positions', []) or []:
                    if p.get('signal_id'):
                        ids.append(p['signal_id'])
                for t in b.get('closed_trades', []) or []:
                    if t.get('signal_id'):
                        ids.append(t['signal_id'])
            b['executed_signal_ids'] = ids[-MAX_SIGNAL_IDS_PERSIST:]
            b['positions'] = (b.get('positions') or [])[-MAX_POSITIONS_PERSIST:]
            b['closed_trades'] = (b.get('closed_trades') or [])[-MAX_CLOSED_TRADES_PERSIST:]
            b['history'] = (b.get('history') or [])[-MAX_HISTORY_PERSIST:]
        return migrated

    def _persist_state(self) -> None:
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            snapshot = {
                'track': self.state.get('track'),
                'symbol': self.state.get('symbol'),
                'active_strategy_keys': self.state.get('active_strategy_keys', []),
                'active_strategy_key': self.state.get('active_strategy_key'),
                'strategy_registry': self.state.get('strategy_registry'),
                'leverage_default': self.state.get('leverage_default'),
                'books': self.state.get('books', {}),
                'positions': self.state.get('positions', [])[-MAX_POSITIONS_PERSIST:],
                'closed_trades': self.state.get('closed_trades', [])[-MAX_CLOSED_TRADES_PERSIST:],
                'history': self.state.get('history', [])[-MAX_HISTORY_PERSIST:],
                'latest': self.state.get('latest'),
                'latest_by_strategy': self.state.get('latest_by_strategy', {}),
                'executed_signal_ids': self.state.get('executed_signal_ids', [])[-MAX_SIGNAL_IDS_PERSIST:],
                'risk_limits': self.state.get('risk_limits'),
                'fee_model': self.state.get('fee_model'),
                'execution_fee_assumption': self.state.get('execution_fee_assumption'),
                'metrics': self.state.get('metrics'),
                'learning': self.state.get('learning'),
            }
            self._backup_state_file('pre-save')
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
            'track', 'symbol', 'active_strategy_keys', 'active_strategy_key', 'leverage_default', 'books',
            'positions', 'closed_trades', 'history', 'latest', 'latest_by_strategy', 'executed_signal_ids',
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

        # Migration: move legacy top-level arrays into per-strategy books when needed.
        books = self.state.get('books') if isinstance(self.state.get('books'), dict) else {}
        if self._legacy_migration_needed(books, data):
            self._backup_state_file('pre-migration', force=True)
            books = self._migrate_legacy_into_books(books or {k: blank_book() for k in merged_registry.keys()}, data)
        self.state['books'] = books

    def _reconcile_registry_and_metrics(self) -> None:
        registry = self.state.get('strategy_registry') or {}
        if not isinstance(registry, dict):
            registry = {}
        # Ensure code-defined strategies always exist.
        for sk, sv in HL_STRATEGY_REGISTRY.items():
            if sk not in registry or not isinstance(registry.get(sk), dict):
                registry[sk] = dict(sv)
            else:
                # Code-defined registry values are authoritative for role/status labeling.
                merged = dict(registry[sk])
                merged.update(sv)
                registry[sk] = merged
        self.state['strategy_registry'] = registry

        # Route execution using configured active learner list (deterministic single-target execution).
        active_keys = [k for k in HL_ACTIVE_STRATEGY_KEYS if k in registry]
        if not active_keys:
            active_keys = ['hl_15m_trend_follow_momo_gate_v1' if 'hl_15m_trend_follow_momo_gate_v1' in registry else 'hl_15m_trend_follow']
        self.state['active_strategy_keys'] = active_keys
        self.state['active_strategy_key'] = active_keys[0]

        books = self.state.get('books') if isinstance(self.state.get('books'), dict) else {}
        for sk in registry.keys():
            if sk not in books or not isinstance(books.get(sk), dict):
                books[sk] = blank_book()
            else:
                books[sk].setdefault('positions', [])
                books[sk].setdefault('closed_trades', [])
                books[sk].setdefault('history', [])
                books[sk].setdefault('executed_signal_ids', [])
                books[sk].setdefault('latest', None)
                books[sk]['positions'] = (books[sk].get('positions') or [])[-MAX_POSITIONS_PERSIST:]
                books[sk]['closed_trades'] = (books[sk].get('closed_trades') or [])[-MAX_CLOSED_TRADES_PERSIST:]
                books[sk]['history'] = (books[sk].get('history') or [])[-MAX_HISTORY_PERSIST:]
                books[sk]['executed_signal_ids'] = (books[sk].get('executed_signal_ids') or [])[-MAX_SIGNAL_IDS_PERSIST:]
        self.state['books'] = books

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

    def _compute_qty(self, entry_price: float, risk_fraction: float = 1.0) -> float:
        cap_qty = self.risk.max_position_notional_usd / max(entry_price, 1.0)
        base_qty = max(0.001, min(0.03, cap_qty))
        rf = max(0.05, min(float(risk_fraction), 1.0))
        return round(max(0.001, base_qty * rf), 4)

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

    def _build_proposal(self, tick: dict[str, Any], candles: list[dict[str, Any]], regime: dict[str, Any], strategy_key: str) -> dict[str, Any]:
        strategy_cfg = ((self.state.get('strategy_registry') or {}).get(strategy_key, {}) or {})
        actionable_conf_min = float(strategy_cfg.get('actionable_confidence_min', 0.58) or 0.58)
        neutral_probe_allow = bool(strategy_cfg.get('neutral_regime_participation_allow', False))
        min_probe_strength = float(strategy_cfg.get('min_regime_strength_for_probe_entries', 0.50) or 0.50)
        max_probe_risk_fraction = float(strategy_cfg.get('max_probe_risk_fraction', 0.35) or 0.35)

        current_regime = str(regime.get('regime') or '')
        regime_conf = float(regime.get('confidence', 0.0) or 0.0)
        probe_phase = False

        if current_regime in {'trend', 'breakout'}:
            if regime_conf < actionable_conf_min:
                return {'status': 'WAIT', 'reason': 'No futures entry: regime confidence below actionable threshold.'}
        elif neutral_probe_allow and current_regime in {'chop', 'low_edge'} and regime_conf >= min_probe_strength:
            probe_phase = True
        else:
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
        risk_fraction = max_probe_risk_fraction if probe_phase else 1.0
        qty = self._compute_qty(entry, risk_fraction=risk_fraction)
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
            'strategy_key': strategy_key,
            'strategy_family': (self.state.get('strategy_registry', {}).get(strategy_key, {}) or {}).get('family', 'trend_follow'),
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
            'probe_phase': probe_phase,
            'probe_risk_fraction': round2(risk_fraction),
            'actionable_confidence_min': round2(actionable_conf_min),
            'min_regime_strength_for_probe_entries': round2(min_probe_strength),
        }

    def _load_news_context(self) -> dict[str, Any]:
        try:
            return json.loads(NEWS_STATE_FILE.read_text(encoding='utf-8'))
        except Exception:
            return {}

    def _adaptive_leverage(self, strategy_key: str, proposal: dict[str, Any], strategy_cfg: dict[str, Any], lev_cap: float) -> float:
        target = float(strategy_cfg.get('leverage_target', 4.0))

        rg = str(proposal.get('market_regime') or '')
        conf = float(proposal.get('regime_confidence') or 0.0)
        body_atr = float(proposal.get('entry_body_atr_ratio') or 0.0)
        spread_pct = float(proposal.get('spread_pct') or 0.0)

        if rg in {'trend', 'breakout'}:
            target += 0.5
        if conf >= 0.80:
            target += 1.0
        elif conf < 0.55:
            target -= 1.0
        if body_atr >= 0.35:
            target += 0.75
        elif body_atr < 0.18:
            target -= 0.75
        if spread_pct > 0.03:
            target -= 1.0

        overall = ((self.state.get('metrics') or {}).get('strategy_overall') or {}).get(strategy_key, {})
        expectancy = float(overall.get('expectancy_net', 0.0) or 0.0)
        fee_drag = float(overall.get('fee_drag_pct', 0.0) or 0.0)
        if expectancy < 0:
            target -= 0.75
        if fee_drag > 220:
            target -= 0.75

        news = self._load_news_context()
        news_risk = str(news.get('news_risk', 'low'))
        news_conf = str(news.get('source_confidence', 'low'))
        if news_risk == 'high' and news_conf in {'medium', 'high'}:
            target -= 1.5
        elif news_risk == 'medium' and news_conf in {'medium', 'high'}:
            target -= 0.5

        target = max(1.0, min(target, lev_cap))
        return round2(target)

    def _open_from_proposal(self, book: dict[str, Any], proposal: dict[str, Any], tick: dict[str, Any]) -> dict[str, Any]:
        side = proposal['side']
        qty = float(proposal['qty'])
        strategy_key = proposal.get('strategy_key', self.state.get('active_strategy_key', 'hl_15m_trend_follow'))
        strategy_cfg = ((self.state.get('strategy_registry') or {}).get(strategy_key) or {})

        max_positions_cap = int(strategy_cfg.get('max_positions', self.risk.max_positions) or self.risk.max_positions)
        max_pos_notional_cap = float(strategy_cfg.get('max_position_notional_usd', self.risk.max_position_notional_usd) or self.risk.max_position_notional_usd)
        max_total_exposure_cap = float(strategy_cfg.get('max_total_exposure_usd', self.risk.max_total_exposure_usd) or self.risk.max_total_exposure_usd)
        max_leverage_cap = float(strategy_cfg.get('max_leverage', self.risk.max_leverage) or self.risk.max_leverage)

        base_lev = min(max(1.0, float(strategy_cfg.get('leverage_target', self.state['leverage_default']))), max_leverage_cap)
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
        lev_cap = 5.0 if strategy_key == 'hl_15m_trend_follow_conflev_v1' else max_leverage_cap

        probe_phase = bool(proposal.get('probe_phase', False))
        probe_lev_cap = float(strategy_cfg.get('leverage_cap_during_probe_phase', 3.0) or 3.0)
        escalation_gate_enabled = bool(strategy_cfg.get('leverage_escalation_gate_enabled', False))

        if probe_phase:
            lev_cap = min(lev_cap, probe_lev_cap)
        elif not escalation_gate_enabled and strategy_key == 'hl_15m_trend_follow_momo_gate_v1':
            lev_cap = min(lev_cap, probe_lev_cap)

        lev_target = 5.0 if high_conf_5x else self._adaptive_leverage(strategy_key, proposal, strategy_cfg, lev_cap)
        lev = min(max(1.0, float(lev_target)), lev_cap)
        entry = float(proposal['entry_price'])
        notional = entry * qty
        if len(book['positions']) >= max_positions_cap:
            return {'ok': False, 'reason': 'max positions reached'}
        if notional > max_pos_notional_cap:
            return {'ok': False, 'reason': 'position notional exceeds per-position cap'}
        exposure = sum(p['entry_price'] * p['qty'] for p in book['positions'])
        if exposure + notional > max_total_exposure_cap:
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
        book['positions'].append(asdict(p))
        book['executed_signal_ids'].append(proposal['signal_id'])
        book['executed_signal_ids'] = book['executed_signal_ids'][-MAX_SIGNAL_IDS_PERSIST:]
        return {'ok': True, 'position': asdict(p)}

    def _update_positions(self, book: dict[str, Any], tick: dict[str, Any]) -> list[dict[str, Any]]:
        closed = []
        still = []
        for p in book['positions']:
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
        book['positions'] = still
        if closed:
            book['closed_trades'].extend(closed)
            book['closed_trades'] = book['closed_trades'][-MAX_CLOSED_TRADES_PERSIST:]
        return closed

    def _recompute_metrics(self) -> None:
        symbol = self.state.get('symbol', 'ETH-PERP')
        books = self.state.get('books') if isinstance(self.state.get('books'), dict) else {}

        strategy_overall: dict[str, Any] = {}
        strategy_regime: dict[str, Any] = {}
        strategy_symbol: dict[str, Any] = {}

        for strategy_key, book in books.items():
            closed = book.get('closed_trades', []) or []
            openp = book.get('positions', []) or []
            hist = book.get('history', []) or []

            overall = blank_metrics()
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

            strategy_overall[strategy_key] = overall
            strategy_symbol[f"{strategy_key}|{symbol}"] = {**overall}

            for rg in ['trend', 'breakout', 'chop', 'low_edge']:
                k = f"{strategy_key}|{rg}"
                rg_closed = [t for t in closed if t.get('market_regime') == rg]
                rg_open = [p for p in openp if p.get('market_regime') == rg]
                rm = blank_metrics()
                rm['total_closed'] = len(rg_closed)
                rm['open_positions'] = len(rg_open)
                rm['total_opened'] = len(rg_closed) + len(rg_open)
                rm['gross_realized_pnl'] = round2(sum(float(t.get('gross_realized_pnl', 0)) for t in rg_closed))
                rm['net_realized_pnl'] = round2(sum(float(t.get('net_realized_pnl', t.get('realized_pnl', 0))) for t in rg_closed))
                rm['total_fees'] = round2(sum(float(t.get('estimated_total_fees', 0)) for t in rg_closed) + sum(float(p.get('estimated_total_fees', 0)) for p in rg_open))
                rm['tp_closes'] = sum(1 for t in rg_closed if t.get('close_reason') == 'TAKE_PROFIT')
                rm['sl_closes'] = sum(1 for t in rg_closed if t.get('close_reason') == 'STOP_LOSS')
                rm['time_exit_stale_closes'] = sum(1 for t in rg_closed if t.get('close_reason') == 'TIME_EXIT_STALE')
                rm['sample_closed'] = len(rg_closed)
                rm['expectancy_net'] = round2(rm['net_realized_pnl'] / len(rg_closed)) if rg_closed else 0.0
                strategy_regime[k] = rm

        for sk in (self.state.get('strategy_registry') or {}).keys():
            strategy_overall.setdefault(sk, blank_metrics())
            strategy_symbol.setdefault(f"{sk}|{symbol}", blank_metrics())

        self.state['metrics'] = {
            'strategy_overall': strategy_overall,
            'strategy_regime': strategy_regime,
            'strategy_symbol': strategy_symbol,
        }

        # Legacy aggregate views for backward compatibility.
        agg_positions, agg_closed, agg_history, agg_ids = [], [], [], []
        latest_by = {}
        for sk, b in books.items():
            agg_positions.extend(b.get('positions', []))
            agg_closed.extend(b.get('closed_trades', []))
            agg_history.extend(b.get('history', []))
            agg_ids.extend(b.get('executed_signal_ids', []))
            if b.get('latest'):
                latest_by[sk] = b.get('latest')
        self.state['positions'] = agg_positions[-MAX_POSITIONS_PERSIST:]
        self.state['closed_trades'] = agg_closed[-MAX_CLOSED_TRADES_PERSIST:]
        self.state['history'] = agg_history[-MAX_HISTORY_PERSIST:]
        self.state['executed_signal_ids'] = agg_ids[-MAX_SIGNAL_IDS_PERSIST:]
        self.state['latest_by_strategy'] = latest_by

    def apply_research_overrides(self, overrides: dict[str, Any], editable_modes: set[str], editable_fields: set[str]) -> None:
        if not isinstance(overrides, dict):
            return
        registry = self.state.get('strategy_registry') or {}
        if not isinstance(registry, dict):
            return

        changed = False
        for mode, patch in overrides.items():
            if mode not in editable_modes:
                continue
            if mode not in registry or not isinstance(patch, dict):
                continue
            for k, v in patch.items():
                if k not in editable_fields:
                    continue
                registry[mode][k] = v
                changed = True

        if changed:
            self.state['strategy_registry'] = registry
            self._reconcile_registry_and_metrics()

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
        latest_by_strategy: dict[str, Any] = {}

        for strategy_key in self.state.get('active_strategy_keys', []):
            book = self.state['books'].setdefault(strategy_key, blank_book())
            closed_now = self._update_positions(book, tick)
            proposal = self._build_proposal(tick, candles, regime, strategy_key)
            decision = proposal

            if proposal.get('status') == 'PROPOSE_TRADE':
                if strategy_key == 'hl_15m_trend_follow_momo_gate_v1':
                    cfg = (self.state.get('strategy_registry', {}) or {}).get(strategy_key, {})
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
                            'strategy_key': strategy_key,
                            'diagnostics': {
                                'momentum_gate_min_atr_body': round2(min_body_atr),
                                'entry_body_atr_ratio': round2(body_ratio),
                                'atr': round2(atr),
                                'entry_candle_open': round2(float(entry_candle.get('open', 0))) if entry_candle else 0.0,
                                'entry_candle_close': round2(float(entry_candle.get('close', 0))) if entry_candle else 0.0,
                            },
                        }

                if decision.get('status') == 'PROPOSE_TRADE':
                    if proposal['signal_id'] in set(book.get('executed_signal_ids', [])):
                        decision = {'status': 'WAIT', 'reason': 'Duplicate signal skipped in paper simulator.', 'strategy_key': strategy_key}
                    else:
                        opened = self._open_from_proposal(book, proposal, tick)
                        if opened.get('ok'):
                            decision = {
                                'status': 'PAPER_TRADE_OPEN',
                                'reason': 'Controlled paper proposal auto-opened inside Hyperliquid paper track.',
                                'strategy_key': strategy_key,
                                'proposal': proposal,
                            }
                        else:
                            decision = {'status': 'WAIT', 'reason': f"Paper risk guard blocked open: {opened.get('reason')}", 'strategy_key': strategy_key}

            if closed_now:
                decision = {
                    'status': 'PAPER_TRADE_CLOSED',
                    'reason': f"Closed {len(closed_now)} paper position(s) by TP/SL/STALE.",
                    'strategy_key': strategy_key,
                    'closed': closed_now[-3:],
                }

            s_latest = {
                'timestamp': now_iso(),
                'strategy_key': strategy_key,
                'regime': regime,
                'decision': decision,
                'positions_open': len(book.get('positions', [])),
                'positions': (book.get('positions', []) or [])[-MAX_LATEST_POSITIONS_VIEW:],
                'closed_trades': (book.get('closed_trades', []) or [])[-MAX_LATEST_CLOSED_VIEW:],
            }
            book['latest'] = s_latest
            book.setdefault('history', []).append(s_latest)
            book['history'] = book['history'][-MAX_HISTORY_PERSIST:]
            latest_by_strategy[strategy_key] = s_latest

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
            'decision': (latest_by_strategy.get(self.state.get('active_strategy_key', '')) or {}).get('decision', {}),
            'active_strategy_key': self.state.get('active_strategy_key'),
            'active_strategy_keys': self.state.get('active_strategy_keys', []),
            'active_strategy_entry': (self.state.get('strategy_registry', {}) or {}).get(self.state.get('active_strategy_key', 'hl_15m_trend_follow')),
            'risk_limits': self.state['risk_limits'],
            'fee_model': self.state['fee_model'],
            'execution_fee_assumption': self.state.get('execution_fee_assumption', {}),
            'metrics': self.state.get('metrics', {}),
            'latest_by_strategy': latest_by_strategy,
            'positions_open': len(self.state.get('positions', [])),
            'positions': self.state.get('positions', [])[-MAX_LATEST_POSITIONS_VIEW:],
            'closed_trades': self.state.get('closed_trades', [])[-MAX_LATEST_CLOSED_VIEW:],
            'max_positions': self.risk.max_positions,
            'portfolio_summary': {
                'strategies_active': len(self.state.get('active_strategy_keys', [])),
                'open_positions_total': len(self.state.get('positions', [])),
                'net_realized_total': round2(sum(v.get('net_realized_pnl', 0) for v in (self.state.get('metrics', {}).get('strategy_overall', {}) or {}).values())),
            },
        }
        self.state['latest'] = latest
        self.state['latest_by_strategy'] = latest_by_strategy
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
