from __future__ import annotations
import json
import time
from dataclasses import dataclass
import requests
from sqlalchemy.orm import Session
from app.services.agent_decisions import record_decision_packet
from app.services.model_connectors import get_model_registration, _auth_headers
from app.services.jason_agent import (
    _latest_market_snapshot,
    _benchmark_reasoning,
    _load_state,
    _save_state,
    _evaluate_slot_gate,
    _open_trade,
    _close_trade,
    _list_open_trades,
    _load_json_state,
    _default_portfolio_gate,
    PORTFOLIO_GATE_KEY,
)
QWEN_AGENT_ID = 'qwen_local_challenger'
@dataclass
class Decision:
    action: str
    symbol: str
    leverage: float
    allocation_pct: float
    confidence: float
    rationale: str
PROMPT = """Return ONLY compact JSON with keys:
action (hold|long|short|close), symbol, leverage, allocation_pct, confidence, rationale.
Use short rationale, no extra text.
Constraints: leverage<=20, allocation_pct<=50.
"""
def _extract_json(raw: str) -> dict:
    raw = (raw or '').strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    i = raw.find('{')
    j = raw.rfind('}')
    if i >= 0 and j > i:
        try:
            return json.loads(raw[i:j+1])
        except Exception:
            return {}
    return {}
def _context_tier(reg_item: dict) -> tuple[str, int]:
    tiers = (reg_item or {}).get('context_tiers') or {}
    max_ctx = int(tiers.get('fast_decision') or 8000)
    return 'fast_decision', max_ctx
def _estimate_size(obj: dict) -> int:
    try:
        return len(json.dumps(obj, separators=(',', ':')))
    except Exception:
        return 0
def _query_local_openai_compatible(base_url: str, remote_model_id: str, payload: dict, headers: dict | None = None, api_mode: str = 'openai-chat') -> tuple[str, float, dict]:
    started = time.time()
    mode = str(api_mode or 'openai-chat').lower()
    if mode == 'openai-completions':
        url = base_url.rstrip('/') + '/completions'
        body = {
            'model': remote_model_id,
            'prompt': PROMPT + '\n' + json.dumps(payload, separators=(',', ':')),
            'temperature': 0.15,
            'max_tokens': 320,
        }
        r = requests.post(url, json=body, headers=headers or None, timeout=12)
        r.raise_for_status()
        data = r.json() if r.content else {}
        text = ((data.get('choices') or [{}])[0].get('text') or '')
    else:
        url = base_url.rstrip('/') + '/chat/completions'
        body = {
            'model': remote_model_id,
            'messages': [
                {'role': 'system', 'content': PROMPT},
                {'role': 'user', 'content': json.dumps(payload, separators=(',', ':'))},
            ],
            'temperature': 0.15,
            'max_tokens': 320,
        }
        r = requests.post(url, json=body, headers=headers or None, timeout=12)
        r.raise_for_status()
        data = r.json() if r.content else {}
        text = (((data.get('choices') or [{}])[0].get('message') or {}).get('content') or '')
    latency = (time.time() - started) * 1000.0
    return text, latency, data
def run_qwen_once(db: Session):
    reg = get_model_registration(db, 'qwen3.5-9b-local')
    if not reg.get('ok'):
        return {'ok': False, 'error': 'qwen_model_not_registered'}
    model = reg['item'] or {}
    if not bool(model.get('paper_only', True)):
        return {'ok': False, 'error': 'qwen_must_be_paper_only'}
    snapshot = _latest_market_snapshot(db)
    if not snapshot:
        return {'ok': False, 'error': 'no_market_snapshot'}
    state = _load_state(db)
    open_trades = _list_open_trades(db)
    tier, ctx_limit = _context_tier(model)
    request_payload = {
        'goal': 'maximize paper pnl under risk caps',
        'context_tier': tier,
        'context_limit': ctx_limit,
        'state': {'balance_usd': state.get('balance_usd'), 'open_positions': len(open_trades)},
        'market_snapshot': snapshot,
        'tradable_symbols': list(snapshot.keys())[:120],
        'constraints': {'max_leverage': 20, 'max_allocation_pct': 50, 'paper_only': True},
    }
    raw_text = ''
    latency_ms = None
    parse_ok = False
    repair_used = False
    out_size = 0
    in_size = _estimate_size(request_payload)
    try:
        raw_text, latency_ms, _resp = _query_local_openai_compatible(
            str(model.get('base_url') or ''),
            str(model.get('remote_model_id') or ''),
            request_payload,
            headers=_auth_headers(model),
            api_mode=str(model.get('api_mode') or 'openai-completions'),
        )
        out_size = len(raw_text or '')
    except Exception as exc:
        record_decision_packet(
            db,
            agent_id=QWEN_AGENT_ID,
            symbol='BTC',
            action='hold',
            confidence=0.01,
            rationale=f'Qwen endpoint failure: {str(exc)[:180]}',
            context={'decision_source': 'local_qwen', 'context_tier': tier, 'telemetry': {'input_size': in_size, 'auth_mode': str(model.get('auth_mode') or 'none')}},
            risk={'paper_only': True},
            execution={'mode': 'virtual_hyperliquid_perps', 'result': {'error': 'provider_unavailable'}, 'decision_source': 'local_qwen'},
            outcome={'quality_state': 'failed_provider'},
        )
        db.commit()
        return {'ok': False, 'error': 'provider_unavailable'}
    obj = _extract_json(raw_text)
    if not obj:
        repair_used = True
        # hard repair fallback
        obj = {'action': 'hold', 'symbol': 'BTC', 'leverage': 1, 'allocation_pct': 0, 'confidence': 0.2, 'rationale': 'parse_repair_fallback'}
    action = str(obj.get('action') or 'hold').lower()
    if action not in ('hold', 'long', 'short', 'close'):
        action = 'hold'; repair_used = True
    symbol = str(obj.get('symbol') or 'BTC').upper()
    if symbol not in snapshot:
        symbol = 'BTC' if 'BTC' in snapshot else next(iter(snapshot.keys()))
        repair_used = True
    lev = max(1.0, min(20.0, float(obj.get('leverage') or 1.0)))
    alloc = max(0.0, min(50.0, float(obj.get('allocation_pct') or 0.0)))
    conf = max(0.01, min(1.0, float(obj.get('confidence') or 0.2)))
    rationale = str(obj.get('rationale') or '').strip()[:400]
    if not rationale:
        rationale = f'{action} {symbol} local-qwen concise decision'; repair_used = True
    parse_ok = True
    d = Decision(action=action, symbol=symbol, leverage=lev, allocation_pct=alloc, confidence=conf, rationale=rationale)
    result = {'decision': d.__dict__, 'telemetry': {
        'model_id': 'qwen3.5-9b-local',
        'model_source': 'local_openai_compatible',
        'context_tier': tier,
        'input_size_estimate': in_size,
        'output_size': out_size,
        'latency_ms': latency_ms,
        'parse_success': parse_ok,
        'repair_used': repair_used,
        'auth_mode': str(model.get('auth_mode') or 'none'),
        'size_clip_applied': bool('[size_clipped_to_gate]' in (d.rationale or '')),
    }}
    if d.action in ('long', 'short'):
        gate = _evaluate_slot_gate(db, d, state, open_trades)
        result['gating'] = gate
        if gate.get('allowed'):
            px = float((snapshot.get(d.symbol) or {}).get('mid_price') or 0)
            if px > 0:
                result['open'] = _open_trade(db, d, state, px, gate_trace=gate)
        else:
            result['open_denied'] = True
    elif d.action == 'close':
        target = next((t for t in reversed(open_trades) if str(t.get('symbol')).upper() == d.symbol), None)
        if target:
            px = float((snapshot.get(d.symbol) or {}).get('mid_price') or 0)
            if px > 0:
                result['close'] = _close_trade(db, target, px, d.rationale, state)
    state['open_positions'] = len(_list_open_trades(db))
    _save_state(db, state)
    quality_state = 'ok' if (parse_ok and not repair_used) else ('repaired' if parse_ok else 'failed_parse')
    record_decision_packet(
        db,
        agent_id=QWEN_AGENT_ID,
        symbol=d.symbol,
        action=d.action,
        confidence=d.confidence,
        rationale=d.rationale,
        context={'decision_source': 'local_qwen', 'context_tier': tier, 'benchmark_reasoning': _benchmark_reasoning(snapshot)},
        risk={'paper_only': True, 'max_leverage': 20, 'max_allocation_pct': 50},
        execution={'mode': 'virtual_hyperliquid_perps', 'decision_source': 'local_qwen', 'result': result},
        outcome={'balance_usd': state.get('balance_usd'), 'quality_state': quality_state},
    )
    db.commit()
    return {'ok': True, 'agent_id': QWEN_AGENT_ID, **result, 'quality_state': quality_state}
