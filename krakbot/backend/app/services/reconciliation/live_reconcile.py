from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from app.api.models import runtime_settings
from app.models.db_models import PositionDB, ReconciliationRunDB
from app.services.execution.broker_router import get_broker


def reconcile_positions(db: Session) -> dict:
    broker = get_broker(runtime_settings.mode.execution_mode)
    broker_positions = broker.get_positions()

    now = datetime.now(timezone.utc)
    existing_rows = {r.symbol: r for r in db.query(PositionDB).all()}
    existing_count = len([r for r in existing_rows.values() if abs(float(r.qty or 0.0)) > 1e-9])

    seen = set()
    drift = []
    for p in broker_positions:
        symbol = p.get("symbol")
        if not symbol:
            continue
        seen.add(symbol)
        qty = float(p.get("qty") or 0.0)
        entry = float(p.get("entry_px") or 0.0)

        prev = existing_rows.get(symbol)
        if prev and abs(float(prev.qty or 0.0) - qty) > 1e-6:
            drift.append({"symbol": symbol, "before_qty": float(prev.qty or 0.0), "after_qty": qty})

        if not prev:
            row = PositionDB(symbol=symbol, qty=qty, avg_entry=entry, mode=runtime_settings.mode.execution_mode, updated_at=now)
            db.add(row)
        else:
            prev.qty = qty
            prev.avg_entry = entry
            prev.mode = runtime_settings.mode.execution_mode
            prev.updated_at = now

    for symbol, row in existing_rows.items():
        if symbol not in seen and abs(float(row.qty or 0.0)) > 1e-9:
            drift.append({"symbol": symbol, "before_qty": float(row.qty or 0.0), "after_qty": 0.0})
            row.qty = 0.0
            row.updated_at = now

    recon = ReconciliationRunDB(
        recon_id=f"recon_{uuid.uuid4().hex[:12]}",
        mode=runtime_settings.mode.execution_mode,
        broker_position_count=len(broker_positions),
        local_position_count=existing_count,
        drift_count=len(drift),
        status="alert" if drift else "ok",
        payload={"drift": drift},
        created_at=now,
    )
    db.add(recon)
    db.commit()

    return {
        "ok": True,
        "count": len(broker_positions),
        "mode": runtime_settings.mode.execution_mode,
        "drift_count": len(drift),
        "alerts": drift,
        "status": "alert" if drift else "ok",
    }
