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


ALLOWED_SYMBOLS = ['BTC', 'ETH', 'SOL']
JASON_AGENT_ID = 'jason'
INITIAL_BALANCE = 1000.0


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
- symbol: one of [\"BTC\",\"ETH\",\"SOL\"]
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


def _latest_market_snapshot(db: Session) -> dict:
    rows = db.execute(
        text(
            """
            SELECT symbol, ts, mid_price, ret_1, ret_5, ret_15
            FROM hyperliquid_training_features
            WHERE symbol IN ('BTC','ETH','SOL')
            ORDER BY ts DESC
            LIMIT 200
            """
        )
    ).mappings().all()
    out: dict[str, dict] = {}
    for r in rows:
        sym = str(r.get('symbol') or '').upper()
        if sym in ALLOWED_SYMBOLS and sym not in out:
            out[sym] = {
                'ts': int(r.get('ts') or 0),
                'mid_price': float(r.get('mid_price') or 0.0),
                'ret_1': float(r.get('ret_1') or 0.0),
                'ret_5': float(r.get('ret_5') or 0.0),
                'ret_15': float(r.get('ret_15') or 0.0),
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
    if symbol not in ALLOWED_SYMBOLS:
        symbol = 'BTC'
    leverage = float(data.get('leverage') or 1)
    allocation_pct = float(data.get('allocation_pct') or 0)
    confidence = float(data.get('confidence') or 0)
    rationale = str(data.get('rationale') or 'No rationale provided')[:1000]
    return Decision(action=action, symbol=symbol, leverage=leverage, allocation_pct=allocation_pct, confidence=confidence, rationale=rationale)


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

    open_trade = _get_open_trade(db)
    decision = _ask_openai(snapshot, state, open_trade)

    results: dict = {'decision': decision.__dict__}

    # Optional close/switch behavior
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

    _save_state(db, state)

    record_decision_packet(
        db,
        agent_id=JASON_AGENT_ID,
        symbol=decision.symbol,
        action=decision.action,
        confidence=decision.confidence,
        rationale=decision.rationale,
        context={'snapshot': snapshot, 'state': state},
        risk={'max_leverage': 20, 'max_allocation_pct': 50, 'paper_money': True},
        execution={'mode': 'virtual_hyperliquid_perps', 'result': results},
        outcome={'balance_usd': state.get('balance_usd')},
    )

    db.commit()
    return {'ok': True, 'agent_id': JASON_AGENT_ID, 'state': state, **results}


def get_jason_state(db: Session):
    state = _load_state(db)
    open_trade = _get_open_trade(db)
    return {'ok': True, 'agent_id': JASON_AGENT_ID, 'state': state, 'open_trade': open_trade}


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
    return {'ok': True, 'items': [dict(r) for r in rows]}
