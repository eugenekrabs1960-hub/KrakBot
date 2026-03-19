from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.models import runtime_settings
from app.core.database import get_db
from app.models.db_models import ExecutionRecordDB, DecisionOutputDB
from app.services.execution.broker_router import get_broker

router = APIRouter(tags=['positions'])


def _paper_positions_from_exec(exec_rows: list[dict]) -> list[dict]:
    net: dict[str, float] = {}
    last_fill: dict[str, dict] = {}
    for e in exec_rows:
        if e.get('status') != 'filled':
            continue
        sym = e.get('symbol')
        if not sym:
            continue
        px = float(e.get('fill_price') or 100.0)
        notional = float(e.get('filled_notional_usd') or e.get('notional_usd') or 0.0)
        qty = (notional / px) if px > 0 else 0.0
        if e.get('action') == 'short':
            qty = -qty
        net[sym] = net.get(sym, 0.0) + qty
        last_fill[sym] = e

    out = []
    for sym, qty in net.items():
        if abs(qty) <= 1e-9:
            continue
        f = last_fill.get(sym, {})
        out.append({
            'coin': sym.replace('-PERP', ''),
            'symbol': sym,
            'side': 'long' if qty > 0 else 'short',
            'qty': qty,
            'notional_usd': abs(qty) * float(f.get('fill_price') or 100.0),
            'entry_px': f.get('fill_price'),
            'unrealized_pnl': None,
            'mode': 'paper',
            'opened_at': f.get('created_at'),
        })
    return out


@router.get('/positions')
def positions(db: Session = Depends(get_db)):
    mode = runtime_settings.mode.execution_mode

    dec_rows = db.query(DecisionOutputDB).order_by(desc(DecisionOutputDB.generated_at)).limit(300).all()
    latest_setup_by_symbol = {}
    for d in dec_rows:
        p = d.payload or {}
        sym = p.get('symbol')
        if sym and sym not in latest_setup_by_symbol:
            latest_setup_by_symbol[sym] = p.get('setup_type')

    exec_rows = [r.payload for r in db.query(ExecutionRecordDB).order_by(desc(ExecutionRecordDB.created_at)).all()]

    if mode == 'paper':
        items = _paper_positions_from_exec(exec_rows)
    else:
        broker = get_broker(mode)
        raw = broker.get_positions()
        items = []
        for p in raw:
            sym = p.get('symbol')
            qty = float(p.get('qty') or 0.0)
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
                'unrealized_pnl': p.get('unrealized_pnl'),
                'mode': mode,
                'opened_at': None,
            })

    for it in items:
        it['setup_type'] = latest_setup_by_symbol.get(it.get('symbol'))

    return {'items': items, 'mode': mode}
