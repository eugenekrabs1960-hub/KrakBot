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




def _calc_unrealized_for_leg(side: str, qty: float, entry_px: float, mark_px: float | None) -> float | None:
    if mark_px is None or entry_px <= 0 or qty <= 0:
        return None
    if side == 'long':
        return (mark_px - entry_px) * qty
    return (entry_px - mark_px) * qty


def _paper_open_legs_from_exec(exec_rows: list[dict], decision_by_packet: dict[str, dict]) -> list[dict]:
    rows = sorted(exec_rows, key=lambda e: e.get('created_at') or '')
    open_lots_by_symbol: dict[str, list[dict]] = {}

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

        side = 'short' if e.get('action') == 'short' else 'long'
        qty = notional / px
        if qty <= 0:
            continue

        lots = open_lots_by_symbol.setdefault(sym, [])
        opposite = 'short' if side == 'long' else 'long'

        # reduce opposite-side open lots first (FIFO)
        remaining = qty
        for lot in lots:
            if remaining <= 1e-12:
                break
            if lot.get('side') != opposite:
                continue
            lq = float(lot.get('remaining_qty') or 0.0)
            if lq <= 1e-12:
                continue
            consume = min(lq, remaining)
            lot['remaining_qty'] = lq - consume
            remaining -= consume

        # prune exhausted lots
        lots[:] = [lot for lot in lots if float(lot.get('remaining_qty') or 0.0) > 1e-12]

        # any remainder opens a new lot in incoming side
        if remaining > 1e-12:
            pkt = e.get('packet_id')
            dec = decision_by_packet.get(pkt or '', {}) if pkt else {}
            lots.append({
                'leg_id': e.get('execution_id') or f"leg_{len(lots)+1}",
                'execution_id': e.get('execution_id'),
                'packet_id': pkt,
                'symbol': sym,
                'coin': sym.replace('-PERP', ''),
                'side': side,
                'entry_px': px,
                'entry_notional_usd': round(remaining * px, 8),
                'entry_qty': remaining,
                'remaining_qty': remaining,
                'leverage': _safe_float(e.get('leverage') or 1.0, 1.0),
                'setup_type': dec.get('setup_type'),
                'opened_at': e.get('created_at'),
            })

    out: list[dict] = []
    for sym, lots in open_lots_by_symbol.items():
        coin = sym.replace('-PERP', '')
        m = fetch_market_snapshot(coin)
        mark = _safe_float(m.get('mark_price') or m.get('last_price'))
        mark_px = mark if mark > 0 else None

        for lot in lots:
            rq = float(lot.get('remaining_qty') or 0.0)
            if rq <= 1e-12:
                continue
            entry_px = _safe_float(lot.get('entry_px'))
            lot_out = dict(lot)
            lot_out['remaining_notional_usd'] = (rq * mark_px) if mark_px else None
            lot_out['mark_px'] = mark_px
            lot_out['unrealized_pnl'] = _calc_unrealized_for_leg(str(lot.get('side')), rq, entry_px, mark_px)
            out.append(lot_out)

    out.sort(key=lambda x: x.get('opened_at') or '', reverse=True)
    return out


def _aggregate_summary_from_open_legs(open_legs: list[dict]) -> list[dict]:
    by_symbol: dict[str, dict] = {}
    for leg in open_legs:
        sym = leg.get('symbol')
        if not sym:
            continue
        side = leg.get('side')
        sign = 1.0 if side == 'long' else -1.0
        qty = float(leg.get('remaining_qty') or 0.0)
        entry_px = _safe_float(leg.get('entry_px'))
        lev = _safe_float(leg.get('leverage') or 1.0, 1.0)
        opened = leg.get('opened_at')
        st = by_symbol.get(sym)
        if not st:
            st = {
                'coin': leg.get('coin') or sym.replace('-PERP',''),
                'symbol': sym,
                'net_qty': 0.0,
                'entry_notional_abs_sum': 0.0,
                'entry_notional_signed_sum': 0.0,
                'weighted_leverage_num': 0.0,
                'opened_at': opened,
                'setup_type': leg.get('setup_type'),
                'mark_px': leg.get('mark_px'),
                'unrealized_pnl': 0.0,
            }
        signed_qty = sign * qty
        st['net_qty'] += signed_qty
        entry_notional_abs = abs(qty * entry_px)
        st['entry_notional_abs_sum'] += entry_notional_abs
        st['entry_notional_signed_sum'] += signed_qty * entry_px
        st['weighted_leverage_num'] += entry_notional_abs * lev
        st['unrealized_pnl'] += _safe_float(leg.get('unrealized_pnl') or 0.0, 0.0)
        if opened and (not st.get('opened_at') or str(opened) < str(st.get('opened_at'))):
            st['opened_at'] = opened
        if not st.get('setup_type') and leg.get('setup_type'):
            st['setup_type'] = leg.get('setup_type')
        if leg.get('mark_px'):
            st['mark_px'] = leg.get('mark_px')
        by_symbol[sym] = st

    out: list[dict] = []
    for sym, st in by_symbol.items():
        net_qty = float(st['net_qty'])
        if abs(net_qty) <= 1e-9:
            continue
        entry_px = abs(st['entry_notional_signed_sum'] / net_qty) if abs(net_qty) > 1e-12 else None
        mark_px = st.get('mark_px')
        notional_usd = abs(net_qty) * mark_px if mark_px else None
        weighted_leverage = (st['weighted_leverage_num'] / st['entry_notional_abs_sum']) if st['entry_notional_abs_sum'] > 1e-12 else 1.0
        out.append({
            'coin': st['coin'],
            'symbol': sym,
            'side': 'long' if net_qty > 0 else 'short',
            'qty': net_qty,
            'notional_usd': notional_usd,
            'entry_px': entry_px,
            'mark_px': mark_px,
            'unrealized_pnl': st['unrealized_pnl'],
            'mode': 'paper',
            'opened_at': st.get('opened_at'),
            'setup_type': st.get('setup_type'),
            'leverage': weighted_leverage,
            'leverage_label': 'weighted_effective',
        })
    out.sort(key=lambda x: x.get('coin') or '')
    return out

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
            'last_leverage': 1.0,
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
        st['last_leverage'] = _safe_float(e.get('leverage') or st.get('last_leverage') or 1.0, 1.0)
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
            'leverage': _safe_float(st.get('last_leverage') or 1.0, 1.0),
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
        open_legs = _paper_open_legs_from_exec(exec_rows, decision_by_packet)
        summary_items = _aggregate_summary_from_open_legs(open_legs)
        # backward-compatible alias for older clients
        items = summary_items
    else:
        open_legs = []
        summary_items = []
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

    return {'items': items, 'summary_items': summary_items if mode == 'paper' else items, 'open_legs': open_legs, 'mode': mode}
