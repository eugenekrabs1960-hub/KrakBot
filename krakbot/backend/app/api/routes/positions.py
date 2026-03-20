from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.models import runtime_settings
from app.core.database import get_db
from app.models.db_models import ExecutionRecordDB, DecisionOutputDB
from app.services.execution.broker_router import get_broker
from app.services.ingest.hyperliquid_market import fetch_market_snapshot

router = APIRouter(tags=['positions'])


def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def _paper_positions_from_exec(exec_rows: list[dict], decision_by_packet: dict[str, dict], non_unclear_setup_by_symbol: dict[str, str]) -> list[dict]:
    # chronological reconstruction for weighted avg entry + open timestamp + setup linkage
    rows = sorted(exec_rows, key=lambda e: e.get('created_at') or '')
    state: dict[str, dict] = {}

    for e in rows:
        if e.get('status') != 'filled':
            continue
        sym = e.get('symbol')
        if not sym:
            continue
        px = _safe_float(e.get('fill_price'), 0.0)
        notional = _safe_float(e.get('filled_notional_usd') or e.get('notional_usd'), 0.0)
        if px <= 0 or notional <= 0:
            continue
        signed_qty = notional / px
        if e.get('action') == 'short':
            signed_qty = -signed_qty

        st = state.get(sym, {
            'qty': 0.0,
            'avg_entry': 0.0,
            'opened_at': None,
            'open_packet_id': None,
            'last_packet_id': None,
        })

        prev_qty = st['qty']
        new_qty = prev_qty + signed_qty

        if abs(prev_qty) < 1e-12:
            # opening from flat
            st['qty'] = new_qty
            st['avg_entry'] = px if abs(new_qty) > 1e-12 else 0.0
            st['opened_at'] = e.get('created_at')
            st['open_packet_id'] = e.get('packet_id')
        elif prev_qty * signed_qty > 0:
            # same direction add => weighted average entry
            abs_prev = abs(prev_qty)
            abs_add = abs(signed_qty)
            st['avg_entry'] = ((st['avg_entry'] * abs_prev) + (px * abs_add)) / (abs_prev + abs_add)
            st['qty'] = new_qty
        else:
            # reducing or flipping
            if abs(new_qty) < 1e-12:
                # fully closed
                st['qty'] = 0.0
                st['avg_entry'] = 0.0
                st['opened_at'] = None
                st['open_packet_id'] = None
            elif prev_qty * new_qty > 0:
                # partial reduce, still same side remains: avg entry unchanged
                st['qty'] = new_qty
            else:
                # flip side: remainder opens new position at this fill price
                st['qty'] = new_qty
                st['avg_entry'] = px
                st['opened_at'] = e.get('created_at')
                st['open_packet_id'] = e.get('packet_id')

        st['last_packet_id'] = e.get('packet_id')
        state[sym] = st

    out = []
    for sym, st in state.items():
        qty = _safe_float(st.get('qty'))
        if abs(qty) <= 1e-9:
            continue

        coin = sym.replace('-PERP', '')
        m = fetch_market_snapshot(coin)
        mark = _safe_float(m.get('mark_price') or m.get('last_price'))
        entry = _safe_float(st.get('avg_entry'))

        notional = abs(qty) * mark if mark > 0 else None
        if entry > 0 and mark > 0:
            unreal = (mark - entry) * qty
        else:
            unreal = None

        setup = None
        open_pkt = st.get('open_packet_id')
        if open_pkt and open_pkt in decision_by_packet:
            setup = decision_by_packet[open_pkt].get('setup_type')
        if not setup or setup == 'unclear':
            last_pkt = st.get('last_packet_id')
            if last_pkt and last_pkt in decision_by_packet:
                setup = decision_by_packet[last_pkt].get('setup_type')
        if not setup or setup == 'unclear':
            setup = non_unclear_setup_by_symbol.get(sym)

        out.append({
            'coin': coin,
            'symbol': sym,
            'side': 'long' if qty > 0 else 'short',
            'qty': qty,
            'notional_usd': notional,
            'entry_px': entry if entry > 0 else None,
            'mark_px': mark if mark > 0 else None,
            'unrealized_pnl': unreal,
            'mode': 'paper',
            'opened_at': st.get('opened_at'),
            'setup_type': setup,
            'leverage': 1.0,
        })
    return out


@router.get('/positions')
def positions(db: Session = Depends(get_db)):
    mode = runtime_settings.mode.execution_mode

    dec_rows = db.query(DecisionOutputDB).order_by(desc(DecisionOutputDB.generated_at)).limit(1200).all()
    decision_by_packet = {}
    non_unclear_setup_by_symbol = {}
    for d in dec_rows:
        p = d.payload or {}
        pid = p.get('packet_id')
        if pid:
            decision_by_packet[pid] = p
        sym = p.get('symbol')
        st = p.get('setup_type')
        if sym and st and st != 'unclear' and sym not in non_unclear_setup_by_symbol:
            non_unclear_setup_by_symbol[sym] = st

    exec_rows = [r.payload for r in db.query(ExecutionRecordDB).order_by(desc(ExecutionRecordDB.created_at)).all()]

    if mode == 'paper':
        items = _paper_positions_from_exec(exec_rows, decision_by_packet, non_unclear_setup_by_symbol)
    else:
        broker = get_broker(mode)
        raw = broker.get_positions()
        items = []
        for p in raw:
            sym = p.get('symbol')
            qty = _safe_float(p.get('qty'))
            side = 'long' if qty > 0 else 'short' if qty < 0 else 'flat'
            if side == 'flat':
                continue
            items.append({
                'coin': sym.replace('-PERP', ''),
                'symbol': sym,
                'side': side,
                'qty': qty,
                'notional_usd': None,
                'entry_px': p.get('entry_px'),
                'mark_px': p.get('mark_px'),
                'unrealized_pnl': p.get('unrealized_pnl'),
                'mode': mode,
                'opened_at': None,
                'setup_type': None,
                'leverage': float(p.get('leverage') or 1.0),
            })

    return {'items': items, 'mode': mode}
