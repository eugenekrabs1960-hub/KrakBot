from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from pathlib import Path
from dataclasses import dataclass

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.agent_decisions import record_decision_packet


BENCHMARK_SYMBOLS = ['BTC', 'ETH', 'SOL']
JASON_AGENT_ID = 'jason'
INITIAL_BALANCE = 1000.0
RISK_PROFILE_KEY = 'agent_jason_risk_profile'
RISK_PROFILES = {'conservative','balanced','aggressive'}
MAX_SNAPSHOT_AGE_MS = 20 * 60 * 1000
SYMBOL_BLACKLIST_PREFIXES = ('TEST', 'DEV', 'FAKE')
SYMBOL_BLACKLIST_VALUES = {'0G', '2Z'}
TOP100_SYMBOLS = {
    'BTC','ETH','BNB','SOL','XRP','ADA','DOGE','TRX','AVAX','DOT','LINK','MATIC','TON','SHIB','LTC',
    'BCH','NEAR','UNI','ATOM','ETC','ICP','APT','FIL','ARB','OP','AAVE','INJ','XLM','SUI','HBAR',
    'MKR','VET','ALGO','QNT','EGLD','AXS','SAND','MANA','THETA','XTZ','EOS','GRT','FLOW','CHZ','NEO',
    'SNX','KAVA','RUNE','DYDX','CRV','LDO','APE','IMX','GMX','COMP','ZEC','DASH','CAKE','1INCH','ENJ',
    'BAT','WOO','JASMY','IOTA','KSM','ZIL','ROSE','CELO','HOT','QTUM','RVN','ICX','ONT','SC','WAVES',
    'ANKR','XDC','KLAY','MINA','FTM','GALA','BLUR','AR','STX','JTO','JUP','BONK','PEPE','SEI','PYTH',
    'TIA','STRK','PENDLE','WIF','SUSHI','YFI','WLD','ORDI','RAY','RNDR','FET','GNO','CFX','LRC','KAS'
}
BENCHMARK_EXPORT_DIR = Path('/tmp/krakbot_training')
UNIVERSE_KEY = 'agent_jason_tradable_universe'
PORTFOLIO_GATE_KEY = 'agent_jason_portfolio_gate_v1'
BUCKETS_KEY = 'agent_jason_correlation_buckets_v1'


@dataclass
class Decision:
    action: str  # long|short|close|hold
    symbol: str
    leverage: float
    allocation_pct: float
    confidence: float
    rationale: str


SYSTEM_PROMPT = """You are Jason, a hyper-aggressive but rules-constrained paper futures trader.
You must return ONLY JSON with fields:
- action: one of [\"long\",\"short\",\"close\",\"hold\"]
- symbol: one of tradable_symbols provided in prompt (open market)
- leverage: number (1..20)
- allocation_pct: number (0..50) percent of remaining balance
- confidence: number (0..1)
- rationale: short plain text reasoning
Rules:
- Paper money only.
- Max 20x leverage.
- Max 50% of remaining balance per trade.
- If balance <= 0, must hold.
- Use provided market snapshot and recent returns.
"""



def _default_portfolio_gate() -> dict:
    return {
        'enabled': True,
        'max_open_positions': 3,
        'slot_confidence': {'1': 0.60, '2': 0.70, '3': 0.80},
        'max_per_position_allocation_pct': 15.0,
        'max_total_allocation_pct': 45.0,
        'max_same_direction_allocation_pct': 35.0,
        'max_bucket_positions': 2,
        'min_open_interval_sec': 300,
        'slot3_exceptional_confidence': 0.90,
        'require_diversification_for_slot_2_3': True,
    }


def _default_bucket_map() -> dict:
    return {
        'BTC': 'BTC_MAJORS', 'ETH': 'ETH_ECOSYSTEM', 'SOL': 'SOL_ECOSYSTEM',
        'BNB': 'BTC_MAJORS', 'DOGE': 'SPECULATIVE', 'PEPE': 'SPECULATIVE', 'BONK': 'SPECULATIVE',
        'AVAX': 'ALT_L1', 'ADA': 'ALT_L1', 'DOT': 'ALT_L1', 'LINK': 'INFRA',
        'ARB': 'ETH_ECOSYSTEM', 'OP': 'ETH_ECOSYSTEM', 'MATIC': 'ETH_ECOSYSTEM',
        'AAVE': 'ETH_ECOSYSTEM', 'UNI': 'ETH_ECOSYSTEM', 'JTO': 'SOL_ECOSYSTEM',
        'JUP': 'SOL_ECOSYSTEM', 'WIF': 'SPECULATIVE', 'RAY': 'SOL_ECOSYSTEM',
    }


def _load_json_state(db: Session, key: str, default_obj: dict) -> dict:
    row = db.execute(text('SELECT value FROM system_state WHERE key=:k LIMIT 1'), {'k': key}).mappings().first()
    if not row:
        return dict(default_obj)
    v = row.get('value')
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            return dict(default_obj)
    return dict(v) if isinstance(v, dict) else dict(default_obj)


def _save_json_state(db: Session, key: str, obj: dict):
    payload = json.dumps(obj)
    if _dialect_name(db) == 'postgresql':
        db.execute(text('INSERT INTO system_state(key, value, updated_at) VALUES (:k, CAST(:payload AS jsonb), CURRENT_TIMESTAMP) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP'), {'k': key, 'payload': payload})
    else:
        db.execute(text('INSERT INTO system_state(key, value, updated_at) VALUES (:k, :payload, CURRENT_TIMESTAMP) ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP'), {'k': key, 'payload': payload})


def get_portfolio_gate(db: Session):
    return {'ok': True, 'config': _load_json_state(db, PORTFOLIO_GATE_KEY, _default_portfolio_gate())}


def set_portfolio_gate(db: Session, config: dict):
    base = _default_portfolio_gate()
    merged = {**base, **(config or {})}
    merged['slot_confidence'] = {**base['slot_confidence'], **dict((config or {}).get('slot_confidence') or {})}
    _save_json_state(db, PORTFOLIO_GATE_KEY, merged)
    db.commit()
    return {'ok': True, 'config': merged}


def get_correlation_buckets(db: Session):
    return {'ok': True, 'buckets': _load_json_state(db, BUCKETS_KEY, _default_bucket_map())}


def set_correlation_buckets(db: Session, buckets: dict):
    clean = {str(k).upper(): str(v).upper() for k, v in dict(buckets or {}).items() if str(k).strip() and str(v).strip()}
    if not clean:
        return {'ok': False, 'error': 'empty_buckets'}
    _save_json_state(db, BUCKETS_KEY, clean)
    db.commit()
    return {'ok': True, 'buckets': clean}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _extract_json_obj(raw: str) -> dict:
    raw = (raw or '').strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    m = re.search(r'\{[\s\S]*\}', raw)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def _load_state(db: Session) -> dict:
    row = db.execute(text("SELECT value FROM system_state WHERE key='agent_jason_state' LIMIT 1")).mappings().first()
    if not row:
        return {'balance_usd': INITIAL_BALANCE, 'active': True}
    value = row.get('value')
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            value = None
    if not isinstance(value, dict):
        return {'balance_usd': INITIAL_BALANCE, 'active': True}
    value.setdefault('balance_usd', INITIAL_BALANCE)
    value.setdefault('active', True)
    value.setdefault('online', True)
    value.setdefault('hold_streak', 0)
    return value


def _dialect_name(db: Session) -> str:
    dialect = getattr(getattr(db, 'bind', None), 'dialect', None)
    return getattr(dialect, 'name', '')


def _save_state(db: Session, state: dict):
    payload = json.dumps(state)
    dialect_name = _dialect_name(db)
    if dialect_name == 'postgresql':
        db.execute(
            text(
                """
                INSERT INTO system_state(key, value, updated_at)
                VALUES ('agent_jason_state', CAST(:payload AS jsonb), CURRENT_TIMESTAMP)
                ON CONFLICT (key)
                DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                """
            ),
            {'payload': payload},
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO system_state(key, value, updated_at)
                VALUES ('agent_jason_state', :payload, CURRENT_TIMESTAMP)
                ON CONFLICT (key)
                DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                """
            ),
            {'payload': payload},
        )



def _load_risk_profile(db: Session) -> str:
    row = db.execute(text("SELECT value FROM system_state WHERE key=:k LIMIT 1"), {'k': RISK_PROFILE_KEY}).mappings().first()
    if not row:
        return 'balanced'
    value = row.get('value')
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            value = {'profile': value}
    profile = str((value or {}).get('profile') or 'balanced').lower()
    return profile if profile in RISK_PROFILES else 'balanced'


def set_risk_profile(db: Session, profile: str):
    p = str(profile or '').lower().strip()
    if p not in RISK_PROFILES:
        return {'ok': False, 'error': 'invalid_profile', 'allowed': sorted(RISK_PROFILES)}
    payload = json.dumps({'profile': p})
    if _dialect_name(db) == 'postgresql':
        db.execute(text("""
            INSERT INTO system_state(key, value, updated_at)
            VALUES (:k, CAST(:payload AS jsonb), CURRENT_TIMESTAMP)
            ON CONFLICT (key)
            DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
        """), {'k': RISK_PROFILE_KEY, 'payload': payload})
    else:
        db.execute(text("""
            INSERT INTO system_state(key, value, updated_at)
            VALUES (:k, :payload, CURRENT_TIMESTAMP)
            ON CONFLICT (key)
            DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
        """), {'k': RISK_PROFILE_KEY, 'payload': payload})
    db.commit()
    return {'ok': True, 'profile': p}


def get_risk_profile(db: Session):
    return {'ok': True, 'profile': _load_risk_profile(db), 'allowed': sorted(RISK_PROFILES)}





def _load_tradable_universe(db: Session) -> set[str]:
    row = db.execute(text("SELECT value FROM system_state WHERE key=:k LIMIT 1"), {'k': UNIVERSE_KEY}).mappings().first()
    if not row:
        return set(TOP100_SYMBOLS)
    v = row.get('value')
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            v = {'symbols': []}
    symbols = [str(x).upper().strip() for x in (v or {}).get('symbols', []) if str(x).strip()]
    out = {x for x in symbols if re.match(r'^[A-Z][A-Z0-9]{2,11}$', x)}
    return out or set(TOP100_SYMBOLS)


def get_tradable_universe(db: Session):
    syms = sorted(_load_tradable_universe(db))
    return {'ok': True, 'symbols': syms, 'count': len(syms)}


def set_tradable_universe(db: Session, symbols: list[str]):
    cleaned = sorted({str(x).upper().strip() for x in (symbols or []) if str(x).strip()})
    cleaned = [x for x in cleaned if re.match(r'^[A-Z][A-Z0-9]{2,11}$', x)]
    if len(cleaned) < 3:
        return {'ok': False, 'error': 'universe_too_small'}
    payload = json.dumps({'symbols': cleaned})
    if _dialect_name(db) == 'postgresql':
        db.execute(text("""
            INSERT INTO system_state(key, value, updated_at)
            VALUES (:k, CAST(:payload AS jsonb), CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
        """), {'k': UNIVERSE_KEY, 'payload': payload})
    else:
        db.execute(text("""
            INSERT INTO system_state(key, value, updated_at)
            VALUES (:k, :payload, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
        """), {'k': UNIVERSE_KEY, 'payload': payload})
    db.commit()
    return {'ok': True, 'symbols': cleaned, 'count': len(cleaned)}


def _is_tradable_symbol(sym: str, row: dict, now_ms: int, allowed: set[str]) -> bool:
    s = str(sym or '').upper().strip()
    if not s or len(s) < 3 or len(s) > 12:
        return False
    if not re.match(r'^[A-Z][A-Z0-9]{2,11}$', s):
        return False
    if s in SYMBOL_BLACKLIST_VALUES or any(s.startswith(p) for p in SYMBOL_BLACKLIST_PREFIXES):
        return False
    if s not in allowed:
        return False

    ts = int(row.get('ts') or 0)
    if ts <= 0 or (now_ms - ts) > MAX_SNAPSHOT_AGE_MS:
        return False

    mid = float(row.get('mid_price') or 0.0)
    if mid <= 0:
        return False

    # avoid micro/degenerate quote artifacts and implausible infinities
    if mid < 1e-4 or mid > 10_000_000:
        return False

    # require non-trivial movement signal availability
    r1 = abs(float(row.get('ret_1') or 0.0))
    r5 = abs(float(row.get('ret_5') or 0.0))
    r15 = abs(float(row.get('ret_15') or 0.0))
    if max(r1, r5, r15) == 0:
        return False

    return True


def _latest_market_snapshot(db: Session) -> dict:
    rows = db.execute(
        text(
            """
            SELECT symbol, ts, mid_price, ret_1, ret_5, ret_15
            FROM hyperliquid_training_features
            ORDER BY ts DESC
            LIMIT 5000
            """
        )
    ).mappings().all()
    out: dict[str, dict] = {}
    now_ms = _now_ms()
    allowed = _load_tradable_universe(db)
    for r in rows:
        sym = str(r.get('symbol') or '').upper()
        if sym in out:
            continue
        if not _is_tradable_symbol(sym, r, now_ms, allowed):
            continue
        out[sym] = {
            'ts': int(r.get('ts') or 0),
            'mid_price': float(r.get('mid_price') or 0.0),
            'ret_1': float(r.get('ret_1') or 0.0),
            'ret_5': float(r.get('ret_5') or 0.0),
            'ret_15': float(r.get('ret_15') or 0.0),
        }
    return out



def _benchmark_reasoning(snapshot: dict) -> dict:
    out = {}
    for sym in BENCHMARK_SYMBOLS:
        d = snapshot.get(sym) or {}
        r1 = float(d.get('ret_1') or 0.0)
        r5 = float(d.get('ret_5') or 0.0)
        r15 = float(d.get('ret_15') or 0.0)
        score = r1 * 0.65 + r5 * 0.25 + r15 * 0.10
        bias = 'long' if score > 0 else ('short' if score < 0 else 'hold')
        out[sym] = {
            'bias': bias,
            'score': score,
            'ret_1': r1,
            'ret_5': r5,
            'ret_15': r15,
            'reasoning': f'{sym} benchmark bias={bias} score={score:+.6f} (r1={r1:+.6f}, r5={r5:+.6f}, r15={r15:+.6f})',
        }
    return out

def _list_open_trades(db: Session):
    rows = db.execute(
        text(
            """
            SELECT id, symbol, side, leverage, allocation_pct, margin_usd, entry_price, qty, opened_at_ms
            FROM agent_virtual_trades
            WHERE agent_id=:agent_id AND status='open'
            ORDER BY opened_at_ms ASC, id ASC
            """
        ),
        {'agent_id': JASON_AGENT_ID},
    ).mappings().all()
    return [dict(r) for r in rows]


def _get_open_trade(db: Session):
    trades = _list_open_trades(db)
    return trades[-1] if trades else None


def _close_trade(db: Session, trade: dict, exit_price: float, reason: str, state: dict):
    side = str(trade['side']).lower()
    direction = 1.0 if side == 'long' else -1.0
    entry = float(trade['entry_price'])
    qty = float(trade['qty'])
    pnl = (exit_price - entry) * qty * direction
    balance_after = max(0.0, float(state.get('balance_usd', INITIAL_BALANCE)) + pnl)
    now = _now_ms()
    if _dialect_name(db) == 'postgresql':
        db.execute(
            text(
                """
                UPDATE agent_virtual_trades
                SET status='closed', exit_price=:exit_price, closed_at_ms=:closed_at_ms,
                    realized_pnl_usd=:pnl, balance_after_usd=:balance_after,
                    meta_json = COALESCE(meta_json, '{}'::jsonb) || CAST(:meta_json AS jsonb)
                WHERE id=:id
                """
            ),
            {
                'id': trade['id'],
                'exit_price': exit_price,
                'closed_at_ms': now,
                'pnl': pnl,
                'balance_after': balance_after,
                'meta_json': json.dumps({'close_reason': reason}),
            },
        )
    else:
        db.execute(
            text(
                """
                UPDATE agent_virtual_trades
                SET status='closed', exit_price=:exit_price, closed_at_ms=:closed_at_ms,
                    realized_pnl_usd=:pnl, balance_after_usd=:balance_after, meta_json=:meta_json
                WHERE id=:id
                """
            ),
            {
                'id': trade['id'],
                'exit_price': exit_price,
                'closed_at_ms': now,
                'pnl': pnl,
                'balance_after': balance_after,
                'meta_json': json.dumps({'close_reason': reason}),
            },
        )
    state['balance_usd'] = balance_after
    if balance_after <= 0:
        state['active'] = False
    return {'closed_trade_id': trade['id'], 'realized_pnl_usd': pnl, 'balance_after_usd': balance_after}


def _open_trade(db: Session, decision: Decision, state: dict, price: float, gate_trace: dict | None = None):
    balance = float(state.get('balance_usd', INITIAL_BALANCE))
    alloc = max(0.0, min(50.0, float(decision.allocation_pct)))
    leverage = max(1.0, min(20.0, float(decision.leverage)))
    margin = balance * (alloc / 100.0)
    if margin <= 0 or price <= 0:
        return {'opened': False, 'reason': 'invalid_margin_or_price'}
    notional = margin * leverage
    qty = notional / price
    now = _now_ms()
    if _dialect_name(db) == 'postgresql':
        db.execute(
            text(
                """
                INSERT INTO agent_virtual_trades(
                  agent_id, symbol, side, leverage, allocation_pct, margin_usd,
                  entry_price, qty, status, rationale, opened_at_ms, meta_json
                ) VALUES (
                  :agent_id, :symbol, :side, :leverage, :allocation_pct, :margin,
                  :entry_price, :qty, 'open', :rationale, :opened_at_ms, CAST(:meta_json AS jsonb)
                )
                """
            ),
            {
                'agent_id': JASON_AGENT_ID,
                'symbol': decision.symbol,
                'side': decision.action,
                'leverage': leverage,
                'allocation_pct': alloc,
                'margin': margin,
                'entry_price': price,
                'qty': qty,
                'rationale': decision.rationale,
                'opened_at_ms': now,
                'meta_json': json.dumps({'confidence': decision.confidence, 'gating': gate_trace or {}}),
            },
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO agent_virtual_trades(
                  agent_id, symbol, side, leverage, allocation_pct, margin_usd,
                  entry_price, qty, status, rationale, opened_at_ms, meta_json
                ) VALUES (
                  :agent_id, :symbol, :side, :leverage, :allocation_pct, :margin,
                  :entry_price, :qty, 'open', :rationale, :opened_at_ms, :meta_json
                )
                """
            ),
            {
                'agent_id': JASON_AGENT_ID,
                'symbol': decision.symbol,
                'side': decision.action,
                'leverage': leverage,
                'allocation_pct': alloc,
                'margin': margin,
                'entry_price': price,
                'qty': qty,
                'rationale': decision.rationale,
                'opened_at_ms': now,
                'meta_json': json.dumps({'confidence': decision.confidence, 'gating': gate_trace or {}}),
            },
        )
    return {'opened': True, 'symbol': decision.symbol, 'side': decision.action, 'entry_price': price, 'qty': qty, 'margin_usd': margin, 'leverage': leverage}



def _bucket_for_symbol(sym: str, bucket_map: dict) -> str:
    return str((bucket_map or {}).get(str(sym or '').upper()) or 'SPECULATIVE').upper()


def _evaluate_slot_gate(db: Session, decision: Decision, state: dict, open_trades: list[dict]) -> dict:
    cfg = _load_json_state(db, PORTFOLIO_GATE_KEY, _default_portfolio_gate())
    bucket_map = _load_json_state(db, BUCKETS_KEY, _default_bucket_map())
    slot = len(open_trades) + 1
    trace = {
        'requested_slot': slot,
        'max_open_positions': int(cfg.get('max_open_positions', 3)),
        'required_confidence': float((cfg.get('slot_confidence') or {}).get(str(slot), 1.0)),
        'actual_confidence': float(decision.confidence or 0.0),
        'allowed': True,
        'deny_reason': None,
    }
    if slot > int(cfg.get('max_open_positions', 3)):
        trace.update({'allowed': False, 'deny_reason': 'slot_limit_reached'}); return trace
    if float(decision.confidence or 0.0) < float((cfg.get('slot_confidence') or {}).get(str(slot), 1.0)):
        trace.update({'allowed': False, 'deny_reason': 'confidence_too_low_for_slot'}); return trace
    alloc = float(decision.allocation_pct or 0.0)
    if alloc > float(cfg.get('max_per_position_allocation_pct', 15.0)):
        trace.update({'allowed': False, 'deny_reason': 'projected_allocation_too_high'}); return trace
    total_alloc = sum(float(t.get('allocation_pct') or 0.0) for t in open_trades) + alloc
    trace['projected_total_allocation_pct'] = total_alloc
    if total_alloc > float(cfg.get('max_total_allocation_pct', 45.0)):
        trace.update({'allowed': False, 'deny_reason': 'projected_allocation_too_high'}); return trace
    side = decision.action
    same_dir = sum(float(t.get('allocation_pct') or 0.0) for t in open_trades if str(t.get('side') or '').lower() == side) + alloc
    trace['projected_same_direction_allocation_pct'] = same_dir
    if same_dir > float(cfg.get('max_same_direction_allocation_pct', 35.0)):
        trace.update({'allowed': False, 'deny_reason': 'projected_directional_exposure_too_high'}); return trace
    lw = sum(float(t.get('allocation_pct') or 0.0) * float(t.get('leverage') or 1.0) for t in open_trades) + (alloc * float(decision.leverage or 1.0))
    trace['projected_leverage_weighted_exposure'] = lw
    target_bucket = _bucket_for_symbol(decision.symbol, bucket_map)
    bc = {}
    for t in open_trades:
        b = _bucket_for_symbol(t.get('symbol'), bucket_map); bc[b] = bc.get(b, 0) + 1
    bucket_after = bc.get(target_bucket, 0) + 1
    trace['bucket'] = target_bucket; trace['bucket_open_count_after'] = bucket_after
    if bucket_after > int(cfg.get('max_bucket_positions', 2)):
        trace.update({'allowed': False, 'deny_reason': 'correlation_bucket_limit'}); return trace
    if bool(cfg.get('require_diversification_for_slot_2_3', True)) and slot >= 2:
        similar = any(_bucket_for_symbol(t.get('symbol'), bucket_map) == target_bucket and str(t.get('side') or '').lower() == side for t in open_trades)
        trace['diversification_ok'] = (not similar)
        if similar:
            trace.update({'allowed': False, 'deny_reason': 'correlation_bucket_limit'}); return trace
    now = _now_ms(); last_open = max([int(t.get('opened_at_ms') or 0) for t in open_trades], default=0)
    since_sec = (now - last_open) / 1000.0 if last_open else 999999
    trace['seconds_since_last_open'] = since_sec
    min_sec = int(cfg.get('min_open_interval_sec', 300))
    if since_sec < min_sec:
        if slot == 3 and float(decision.confidence or 0.0) >= float(cfg.get('slot3_exceptional_confidence', 0.90)):
            trace['pacing_ok'] = True
        else:
            trace.update({'allowed': False, 'deny_reason': 'open_too_soon_after_last_position', 'pacing_ok': False}); return trace
    else:
        trace['pacing_ok'] = True
    if bool(state.get('cooldown_active')):
        trace.update({'allowed': False, 'deny_reason': 'cooldown_active'}); return trace
    if bool(state.get('risk_unhealthy')):
        trace.update({'allowed': False, 'deny_reason': 'portfolio_risk_state_unhealthy'}); return trace
    return trace


def _ask_openai(snapshot: dict, state: dict, open_trade: dict | None) -> Decision:
    api_key = settings.openai_api_key.strip()
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY missing')

    prompt = {
        'task': 'decide next trade action',
        'budget': state.get('balance_usd', INITIAL_BALANCE),
        'open_trade': open_trade,
        'market_snapshot': snapshot,
        'tradable_symbols': list(snapshot.keys()),
        'benchmark_symbols': BENCHMARK_SYMBOLS,
        'goal': 'grow balance as much as possible under constraints',
    }

    payload = {
        'model': settings.jason_agent_model,
        'input': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': json.dumps(prompt)},
        ],
        'temperature': 0.2,
    }
    resp = requests.post(
        'https://api.openai.com/v1/responses',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    text_out = body.get('output_text') or ''
    if not text_out:
        output = body.get('output') or []
        chunks = []
        for o in output:
            for c in (o.get('content') or []):
                if c.get('type') in ('output_text', 'text') and c.get('text'):
                    chunks.append(c.get('text'))
        text_out = '\n'.join(chunks)

    data = _extract_json_obj(text_out)
    action = str(data.get('action') or 'hold').lower()
    if action not in ('long', 'short', 'close', 'hold'):
        action = 'hold'
    symbol = str(data.get('symbol') or 'BTC').upper()
    tradable = list(snapshot.keys())
    if symbol not in tradable:
        symbol = 'BTC' if 'BTC' in tradable else (tradable[0] if tradable else 'BTC')
    leverage = float(data.get('leverage') or 1)
    allocation_pct = float(data.get('allocation_pct') or 0)
    confidence = float(data.get('confidence') or 0)
    rationale = str(data.get('rationale') or 'No rationale provided')[:1000]
    return Decision(action=action, symbol=symbol, leverage=leverage, allocation_pct=allocation_pct, confidence=confidence, rationale=rationale)



def _top_signal(snapshot: dict) -> tuple[str, float]:
    best_sym = 'BTC'
    best_score = 0.0
    for sym, d in (snapshot or {}).items():
        try:
            score = float(d.get('ret_1') or 0.0) * 0.65 + float(d.get('ret_5') or 0.0) * 0.25 + float(d.get('ret_15') or 0.0) * 0.10
        except Exception:
            score = 0.0
        if abs(score) > abs(best_score):
            best_sym, best_score = str(sym).upper(), score
    return best_sym, best_score


def _apply_profit_bias(decision: Decision, state: dict, snapshot: dict, open_trade: dict | None, profile: str = 'balanced') -> Decision:
    # Keep hard risk limits, but avoid passive/zero-size behavior when a signal exists.
    sym, score = _top_signal(snapshot)
    p = (profile or 'balanced').lower()
    if p not in RISK_PROFILES:
        p = 'balanced'

    signal_thresh = 0.00020 if p == 'conservative' else (0.00012 if p == 'balanced' else 0.00006)
    min_lev = 2.0 if p == 'conservative' else (3.0 if p == 'balanced' else 5.0)
    min_alloc = 8.0 if p == 'conservative' else (10.0 if p == 'balanced' else 15.0)

    hold_streak = int(state.get('hold_streak') or 0)
    must_trade = (p == 'aggressive' and not open_trade and hold_streak >= 2 and float(state.get('balance_usd', INITIAL_BALANCE)) > 0)

    if decision.action == 'hold' and not open_trade and (abs(score) >= signal_thresh or must_trade) and float(state.get('balance_usd', INITIAL_BALANCE)) > 0:
        direction = 'long' if score >= 0 else 'short'
        decision.action = direction
        decision.symbol = sym
        decision.leverage = max(decision.leverage, min_lev)
        decision.allocation_pct = max(decision.allocation_pct, min_alloc)
        if must_trade:
            decision.leverage = max(decision.leverage, 6.0)
            decision.allocation_pct = max(decision.allocation_pct, 20.0)
        decision.rationale = (decision.rationale or '').strip() or (
            f'Auto-promoted from hold ({p}) on {sym}; '
            + ('forced anti-idle trade after repeated holds.' if must_trade else 'strongest near-term momentum signal.')
        )

    if decision.action in ('long', 'short'):
        decision.leverage = max(decision.leverage, min_lev)
        decision.allocation_pct = max(decision.allocation_pct, min_alloc)

    decision.leverage = max(1.0, min(20.0, float(decision.leverage)))
    decision.allocation_pct = max(0.0, min(50.0, float(decision.allocation_pct)))
    return decision


def _enrich_quality(decision: Decision, snapshot: dict) -> Decision:
    if not str(decision.rationale or '').strip() or str(decision.rationale).strip().lower() == 'no rationale provided':
        m = snapshot.get(decision.symbol) or {}
        decision.rationale = (
            f"{decision.action.upper()} {decision.symbol}: ret_1={float(m.get('ret_1') or 0):+.5f}, "
            f"ret_5={float(m.get('ret_5') or 0):+.5f}, ret_15={float(m.get('ret_15') or 0):+.5f}; "
            "position sized within risk caps."
        )

    if float(decision.confidence or 0.0) <= 0:
        m = snapshot.get(decision.symbol) or {}
        signal = abs(float(m.get('ret_1') or 0.0) * 0.7 + float(m.get('ret_5') or 0.0) * 0.3)
        base = 0.50 if decision.action == 'hold' else 0.56
        decision.confidence = min(0.88, base + min(signal * 400, 0.22))

    decision.confidence = max(0.01, min(1.0, float(decision.confidence)))
    return decision


def _validate_quality_or_fail(decision: Decision) -> tuple[bool, str]:
    rat = str(decision.rationale or '').strip()
    if not rat or rat.lower() == 'no rationale provided':
        return False, 'invalid_rationale'
    conf = float(decision.confidence or 0.0)
    if conf <= 0.0:
        return False, 'invalid_confidence'
    return True, ''


def _apply_decision(db: Session, decision: Decision, state: dict, snapshot: dict, decision_source: str):
    open_trades = _list_open_trades(db)
    results: dict = {'decision': decision.__dict__, 'open_positions_before': len(open_trades)}

    if decision.action == 'close':
        target = next((t for t in reversed(open_trades) if str(t.get('symbol')).upper() == decision.symbol.upper()), None)
        if target is None and open_trades:
            target = open_trades[-1]
        if target:
            px = float((snapshot.get(str(target.get('symbol')).upper()) or {}).get('mid_price') or 0)
            if px > 0:
                results['close'] = _close_trade(db, target, px, decision.rationale, state)
                open_trades = _list_open_trades(db)

    if decision.action in ('long', 'short'):
        same_symbol = [t for t in open_trades if str(t.get('symbol')).upper() == decision.symbol.upper()]
        opp = next((t for t in same_symbol if str(t.get('side')).lower() != decision.action), None)
        if opp:
            px = float((snapshot.get(decision.symbol) or {}).get('mid_price') or 0)
            if px > 0:
                results.setdefault('auto_closes', []).append(_close_trade(db, opp, px, 'flip_symbol_side', state))
                open_trades = _list_open_trades(db)

        already_same = any(str(t.get('symbol')).upper() == decision.symbol.upper() and str(t.get('side')).lower() == decision.action for t in open_trades)
        if not already_same:
            gate = _evaluate_slot_gate(db, decision, state, open_trades)
            results['gating'] = gate
            if gate.get('allowed'):
                px = float((snapshot.get(decision.symbol) or {}).get('mid_price') or 0)
                if px > 0:
                    results['open'] = _open_trade(db, decision, state, px, gate_trace=gate)
            else:
                results['open_denied'] = True

    state['online'] = True
    if 'offline_reason' in state:
        state.pop('offline_reason', None)
    state['open_positions'] = len(_list_open_trades(db))
    _save_state(db, state)

    record_decision_packet(
        db,
        agent_id=JASON_AGENT_ID,
        symbol=decision.symbol,
        action=decision.action,
        confidence=decision.confidence,
        rationale=decision.rationale,
        context={'snapshot': snapshot, 'state': state, 'decision_source': decision_source, 'benchmark_reasoning': _benchmark_reasoning(snapshot)},
        risk={'max_leverage': 20, 'max_allocation_pct': 50, 'paper_money': True},
        execution={'mode': 'virtual_hyperliquid_perps', 'decision_source': decision_source, 'result': results, 'gating': results.get('gating')},
        outcome={'balance_usd': state.get('balance_usd')},
    )

    db.commit()
    return {'ok': True, 'agent_id': JASON_AGENT_ID, 'state': state, **results}


def run_jason_once(db: Session):
    state = _load_state(db)
    snapshot = _latest_market_snapshot(db)
    if not snapshot:
        return {'ok': False, 'error': 'no_market_snapshot'}

    if float(state.get('balance_usd', INITIAL_BALANCE)) <= 0:
        state['active'] = False
        _save_state(db, state)
        db.commit()
        return {'ok': False, 'error': 'balance_zero', 'state': state}

    decision = _ask_openai(snapshot, state, _get_open_trade(db))
    profile = _load_risk_profile(db)
    decision = _apply_profit_bias(decision, state, snapshot, _get_open_trade(db), profile=profile)
    decision = _enrich_quality(decision, snapshot)
    ok, err = _validate_quality_or_fail(decision)
    if not ok:
        set_jason_offline(db, reason=err)
        return {'ok': False, 'error': err, 'state': _load_state(db)}
    return _apply_decision(db, decision, state, snapshot, decision_source='oauth_gpt54')


def run_jason_rule_based_once(db: Session):
    return {'ok': False, 'error': 'fallback_disabled'}

def execute_jason_decision(db: Session, *, action: str, symbol: str, leverage: float, allocation_pct: float, confidence: float, rationale: str, decision_source: str = 'oauth_gpt54'):
    state = _load_state(db)
    snapshot = _latest_market_snapshot(db)
    if not snapshot:
        return {'ok': False, 'error': 'no_market_snapshot'}

    if float(state.get('balance_usd', INITIAL_BALANCE)) <= 0:
        state['active'] = False
        _save_state(db, state)
        db.commit()
        return {'ok': False, 'error': 'balance_zero', 'state': state}

    d = Decision(
        action=str(action or 'hold').lower(),
        symbol=str(symbol or 'BTC').upper(),
        leverage=float(leverage or 1),
        allocation_pct=float(allocation_pct or 0),
        confidence=float(confidence or 0),
        rationale=str(rationale or 'No rationale provided')[:1000],
    )
    if d.action not in ('long', 'short', 'close', 'hold'):
        d.action = 'hold'
    tradable = list(snapshot.keys())
    if d.symbol not in tradable:
        d.symbol = 'BTC' if 'BTC' in tradable else (tradable[0] if tradable else 'BTC')
    d.leverage = max(1.0, min(20.0, d.leverage))
    d.allocation_pct = max(0.0, min(50.0, d.allocation_pct))
    d.confidence = max(0.0, min(1.0, d.confidence))
    d = _apply_profit_bias(d, state, snapshot, _get_open_trade(db), profile=_load_risk_profile(db))
    d = _enrich_quality(d, snapshot)

    ok, err = _validate_quality_or_fail(d)
    if not ok:
        set_jason_offline(db, reason=err)
        return {'ok': False, 'error': err, 'state': _load_state(db)}

    src = str(decision_source or 'oauth_gpt54').lower()
    if src != 'oauth_gpt54':
        return {'ok': False, 'error': 'fallback_disabled'}

    return _apply_decision(db, d, state, snapshot, decision_source=src)



def set_jason_offline(db: Session, *, reason: str = 'oauth_unavailable'):
    state = _load_state(db)
    state['online'] = False
    state['offline_reason'] = str(reason or 'oauth_unavailable')[:200]
    state['last_offline_at_ms'] = _now_ms()
    _save_state(db, state)
    db.commit()
    return {'ok': True, 'agent_id': JASON_AGENT_ID, 'state': state}

def get_jason_state(db: Session):
    state = _load_state(db)
    open_trades = _list_open_trades(db)
    open_trade = open_trades[-1] if open_trades else None
    return {'ok': True, 'agent_id': JASON_AGENT_ID, 'state': state, 'open_trade': open_trade, 'open_trades': open_trades, 'risk_profile': _load_risk_profile(db), 'portfolio_gate': _load_json_state(db, PORTFOLIO_GATE_KEY, _default_portfolio_gate())}



def export_benchmark_reasoning_rows(db: Session, *, agent_id: str = JASON_AGENT_ID, limit: int = 500):
    rows = db.execute(
        text(
            """
            SELECT id, ts, agent_id, symbol, action, confidence, rationale, context_json
            FROM agent_decision_packets
            WHERE agent_id=:agent_id
            ORDER BY id DESC
            LIMIT :limit
            """
        ),
        {'agent_id': agent_id, 'limit': max(1, min(5000, int(limit)))},
    ).mappings().all()

    out = []
    for r in rows:
        ctx = r.get('context_json') or {}
        if isinstance(ctx, str):
            try:
                ctx = json.loads(ctx)
            except Exception:
                ctx = {}
        br = (ctx or {}).get('benchmark_reasoning') or {}
        out.append({
            'packet_id': r.get('id'),
            'ts': r.get('ts'),
            'agent_id': r.get('agent_id'),
            'trade_symbol': r.get('symbol'),
            'trade_action': r.get('action'),
            'trade_confidence': r.get('confidence'),
            'trade_rationale': r.get('rationale'),
            'btc': br.get('BTC') or {},
            'eth': br.get('ETH') or {},
            'sol': br.get('SOL') or {},
        })
    return {'ok': True, 'items': out, 'count': len(out)}


def export_benchmark_reasoning_csv(db: Session, *, agent_id: str = JASON_AGENT_ID, limit: int = 5000):
    payload = export_benchmark_reasoning_rows(db, agent_id=agent_id, limit=limit)
    items = payload.get('items') or []

    BENCHMARK_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    now_ms = _now_ms()
    prefix = f'jason_benchmark_{agent_id}_{now_ms}'
    csv_path = BENCHMARK_EXPORT_DIR / f'{prefix}.csv'
    manifest_path = BENCHMARK_EXPORT_DIR / f'{prefix}.manifest.json'

    fieldnames = [
        'packet_id','ts','agent_id','trade_symbol','trade_action','trade_confidence','trade_rationale',
        'btc_bias','btc_score','btc_ret_1','btc_ret_5','btc_ret_15','btc_reasoning',
        'eth_bias','eth_score','eth_ret_1','eth_ret_5','eth_ret_15','eth_reasoning',
        'sol_bias','sol_score','sol_ret_1','sol_ret_5','sol_ret_15','sol_reasoning',
    ]

    with csv_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for it in items:
            btc = it.get('btc') or {}
            eth = it.get('eth') or {}
            sol = it.get('sol') or {}
            w.writerow({
                'packet_id': it.get('packet_id'),
                'ts': it.get('ts'),
                'agent_id': it.get('agent_id'),
                'trade_symbol': it.get('trade_symbol'),
                'trade_action': it.get('trade_action'),
                'trade_confidence': it.get('trade_confidence'),
                'trade_rationale': it.get('trade_rationale'),
                'btc_bias': btc.get('bias'), 'btc_score': btc.get('score'), 'btc_ret_1': btc.get('ret_1'), 'btc_ret_5': btc.get('ret_5'), 'btc_ret_15': btc.get('ret_15'), 'btc_reasoning': btc.get('reasoning'),
                'eth_bias': eth.get('bias'), 'eth_score': eth.get('score'), 'eth_ret_1': eth.get('ret_1'), 'eth_ret_5': eth.get('ret_5'), 'eth_ret_15': eth.get('ret_15'), 'eth_reasoning': eth.get('reasoning'),
                'sol_bias': sol.get('bias'), 'sol_score': sol.get('score'), 'sol_ret_1': sol.get('ret_1'), 'sol_ret_5': sol.get('ret_5'), 'sol_ret_15': sol.get('ret_15'), 'sol_reasoning': sol.get('reasoning'),
            })

    dataset_hash = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    manifest = {
        'schema_version': 'arena_benchmark_v1',
        'kind': 'jason_benchmark_reasoning',
        'created_at_ms': now_ms,
        'agent_id': agent_id,
        'rows': len(items),
        'limit': limit,
        'dataset_hash_sha256': dataset_hash,
        'file_path': str(csv_path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    return {
        'ok': True,
        'path': str(csv_path),
        'manifest_path': str(manifest_path),
        'rows': len(items),
        'dataset_hash_sha256': dataset_hash,
    }


def list_jason_trades(db: Session, limit: int = 100):
    rows = db.execute(
        text(
            """
            SELECT id, agent_id, symbol, side, leverage, allocation_pct, margin_usd, entry_price,
                   exit_price, qty, status, rationale, opened_at_ms, closed_at_ms,
                   realized_pnl_usd, balance_after_usd
            FROM agent_virtual_trades
            WHERE agent_id=:agent_id
            ORDER BY id DESC
            LIMIT :limit
            """
        ),
        {'agent_id': JASON_AGENT_ID, 'limit': max(1, min(500, int(limit)))},
    ).mappings().all()

    symbols = sorted({str(r.get('symbol') or '').upper() for r in rows if r.get('symbol')})
    latest_px: dict[str, float] = {}
    for sym in symbols:
        px_row = db.execute(
            text(
                """
                SELECT mid_price
                FROM hyperliquid_training_features
                WHERE symbol=:symbol
                ORDER BY ts DESC
                LIMIT 1
                """
            ),
            {'symbol': sym},
        ).mappings().first()
        if px_row and px_row.get('mid_price') is not None:
            latest_px[sym] = float(px_row.get('mid_price') or 0.0)

    items = []
    for r in rows:
        d = dict(r)
        d['unrealized_pnl_usd'] = None
        if str(d.get('status') or '').lower() == 'open':
            sym = str(d.get('symbol') or '').upper()
            px = float(latest_px.get(sym) or 0.0)
            entry = float(d.get('entry_price') or 0.0)
            qty = float(d.get('qty') or 0.0)
            side = str(d.get('side') or '').lower()
            if px > 0 and entry > 0 and qty > 0:
                direction = 1.0 if side == 'long' else -1.0
                d['unrealized_pnl_usd'] = (px - entry) * qty * direction
        items.append(d)

    return {'ok': True, 'items': items}
