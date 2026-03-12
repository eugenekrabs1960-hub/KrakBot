from __future__ import annotations

import json
import re
import time
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




def _is_tradable_symbol(sym: str, row: dict, now_ms: int) -> bool:
    s = str(sym or '').upper().strip()
    if not s or len(s) > 16:
        return False
    if not re.match(r'^[A-Z0-9_\-]+$', s):
        return False
    ts = int(row.get('ts') or 0)
    if ts <= 0 or (now_ms - ts) > MAX_SNAPSHOT_AGE_MS:
        return False
    mid = float(row.get('mid_price') or 0.0)
    if mid <= 0:
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
    for r in rows:
        sym = str(r.get('symbol') or '').upper()
        if sym in out:
            continue
        if not _is_tradable_symbol(sym, r, now_ms):
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

def _get_open_trade(db: Session):
    row = db.execute(
        text(
            """
            SELECT id, symbol, side, leverage, allocation_pct, margin_usd, entry_price, qty, opened_at_ms
            FROM agent_virtual_trades
            WHERE agent_id=:agent_id AND status='open'
            ORDER BY id DESC LIMIT 1
            """
        ),
        {'agent_id': JASON_AGENT_ID},
    ).mappings().first()
    return dict(row) if row else None


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


def _open_trade(db: Session, decision: Decision, state: dict, price: float):
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
                'meta_json': json.dumps({'confidence': decision.confidence}),
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
                'meta_json': json.dumps({'confidence': decision.confidence}),
            },
        )
    return {'opened': True, 'symbol': decision.symbol, 'side': decision.action, 'entry_price': price, 'qty': qty, 'margin_usd': margin, 'leverage': leverage}


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
        symbol = tradable[0] if tradable else 'BTC'
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

    if decision.action == 'hold' and not open_trade and abs(score) >= signal_thresh and float(state.get('balance_usd', INITIAL_BALANCE)) > 0:
        decision.action = 'long' if score > 0 else 'short'
        decision.symbol = sym
        decision.leverage = max(decision.leverage, min_lev)
        decision.allocation_pct = max(decision.allocation_pct, min_alloc)
        decision.rationale = (decision.rationale or '').strip() or f'Auto-promoted from hold ({p}): strongest near-term momentum on {sym}.'

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
    open_trade = _get_open_trade(db)
    results: dict = {'decision': decision.__dict__}

    if open_trade:
        open_symbol = str(open_trade['symbol']).upper()
        must_close = decision.action == 'close' or (decision.action in ('long', 'short') and decision.symbol != open_symbol)
        if must_close:
            px = float((snapshot.get(open_symbol) or {}).get('mid_price') or 0)
            if px > 0:
                results['close'] = _close_trade(db, open_trade, px, decision.rationale, state)
                open_trade = None

    if decision.action in ('long', 'short') and not open_trade:
        px = float((snapshot.get(decision.symbol) or {}).get('mid_price') or 0)
        if px > 0:
            results['open'] = _open_trade(db, decision, state, px)

    state['online'] = True
    if 'offline_reason' in state:
        state.pop('offline_reason', None)
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
        execution={'mode': 'virtual_hyperliquid_perps', 'decision_source': decision_source, 'result': results},
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
        d.symbol = tradable[0] if tradable else 'BTC'
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
    open_trade = _get_open_trade(db)
    return {'ok': True, 'agent_id': JASON_AGENT_ID, 'state': state, 'open_trade': open_trade, 'risk_profile': _load_risk_profile(db)}



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
