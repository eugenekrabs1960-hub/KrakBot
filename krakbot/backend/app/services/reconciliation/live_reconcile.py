from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.api.models import runtime_settings
from app.models.db_models import PositionDB
from app.services.execution.broker_router import get_broker


def reconcile_positions(db: Session) -> dict:
    broker = get_broker(runtime_settings.mode.execution_mode)
    broker_positions = broker.get_positions()

    # upsert normalized positions
    now = datetime.now(timezone.utc)
    seen = set()
    for p in broker_positions:
        symbol = p.get("symbol")
        if not symbol:
            continue
        seen.add(symbol)
        row = db.get(PositionDB, symbol)
        qty = float(p.get("qty") or 0.0)
        entry = float(p.get("entry_px") or 0.0)
        if not row:
            row = PositionDB(symbol=symbol, qty=qty, avg_entry=entry, mode=runtime_settings.mode.execution_mode, updated_at=now)
            db.add(row)
        else:
            row.qty = qty
            row.avg_entry = entry
            row.mode = runtime_settings.mode.execution_mode
            row.updated_at = now

    for row in db.query(PositionDB).all():
        if row.symbol not in seen:
            row.qty = 0.0
            row.updated_at = now

    db.commit()
    return {"ok": True, "count": len(broker_positions), "mode": runtime_settings.mode.execution_mode}
