from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.models import runtime_settings
from app.core.database import get_db
from app.models.db_models import ExecutionRecordDB, DecisionOutputDB
from app.services.execution.broker_router import get_broker

router = APIRouter(tags=['positions'])


@router.get('/positions')
def positions(db: Session = Depends(get_db)):
    broker = get_broker(runtime_settings.mode.execution_mode)
    raw = broker.get_positions()

    dec_rows = db.query(DecisionOutputDB).order_by(desc(DecisionOutputDB.generated_at)).limit(300).all()
    latest_setup_by_symbol = {}
    for d in dec_rows:
        p = d.payload or {}
        sym = p.get('symbol')
        if sym and sym not in latest_setup_by_symbol:
            latest_setup_by_symbol[sym] = p.get('setup_type')

    exec_rows = db.query(ExecutionRecordDB).order_by(desc(ExecutionRecordDB.created_at)).limit(300).all()
    latest_fill = {}
    for e in exec_rows:
        p = e.payload or {}
        sym = p.get('symbol')
        if not sym:
            continue
        if sym not in latest_fill and p.get('status') == 'filled':
            latest_fill[sym] = p

    items = []
    for p in raw:
        sym = p.get('symbol')
        qty = float(p.get('qty') or 0.0)
        fill = latest_fill.get(sym, {})
        side = 'long' if qty > 0 else 'short' if qty < 0 else 'flat'
        items.append({
            'coin': sym.replace('-PERP', ''),
            'symbol': sym,
            'side': side,
            'qty': qty,
            'notional_usd': fill.get('filled_notional_usd') or fill.get('notional_usd'),
            'entry_px': p.get('entry_px'),
            'unrealized_pnl': p.get('unrealized_pnl'),
            'mode': runtime_settings.mode.execution_mode,
            'setup_type': latest_setup_by_symbol.get(sym),
            'opened_at': fill.get('created_at'),
        })

    return {'items': items, 'mode': runtime_settings.mode.execution_mode}
