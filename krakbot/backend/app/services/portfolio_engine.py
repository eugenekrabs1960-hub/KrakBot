import time
import uuid
from sqlalchemy import text
from sqlalchemy.orm import Session


def _get_last_price(db: Session, market: str) -> float:
    row = db.execute(
        text("SELECT price FROM market_trades WHERE market=:market ORDER BY id DESC LIMIT 1"),
        {"market": market},
    ).mappings().first()
    return float(row["price"]) if row else 0.0


def apply_fill(db: Session, strategy_instance_id: str, market: str, side: str, qty: float, fill_price: float):
    row = db.execute(
        text(
            """
            SELECT id, qty, avg_entry_price, realized_pnl_usd
            FROM positions
            WHERE strategy_instance_id=:sid AND market=:market
            """
        ),
        {"sid": strategy_instance_id, "market": market},
    ).mappings().first()

    if not row:
        pos_id = f"pos_{uuid.uuid4().hex[:12]}"
        db.execute(
            text(
                """
                INSERT INTO positions(id, strategy_instance_id, market, side, qty, avg_entry_price, realized_pnl_usd)
                VALUES (:id, :sid, :market, 'long', 0, 0, 0)
                """
            ),
            {"id": pos_id, "sid": strategy_instance_id, "market": market},
        )
        current_qty = 0.0
        avg_entry = 0.0
        realized = 0.0
    else:
        current_qty = float(row["qty"])
        avg_entry = float(row["avg_entry_price"])
        realized = float(row["realized_pnl_usd"])

    if side.lower() == 'buy':
        new_qty = current_qty + qty
        new_avg = ((current_qty * avg_entry) + (qty * fill_price)) / new_qty if new_qty > 0 else 0.0
        new_realized = realized
    else:
        sold = min(qty, current_qty)
        pnl = (fill_price - avg_entry) * sold
        new_realized = realized + pnl
        new_qty = max(current_qty - qty, 0.0)
        new_avg = avg_entry if new_qty > 0 else 0.0

    db.execute(
        text(
            """
            UPDATE positions
            SET qty=:qty, avg_entry_price=:avg, realized_pnl_usd=:realized, updated_at=NOW()
            WHERE strategy_instance_id=:sid AND market=:market
            """
        ),
        {"qty": new_qty, "avg": new_avg, "realized": new_realized, "sid": strategy_instance_id, "market": market},
    )

    # Portfolio equity = starting + realized + unrealized
    start_row = db.execute(
        text("SELECT starting_equity_usd FROM paper_portfolios WHERE strategy_instance_id=:sid"),
        {"sid": strategy_instance_id},
    ).mappings().first()
    starting = float(start_row["starting_equity_usd"]) if start_row else 10000.0
    mark = _get_last_price(db, market) or fill_price
    unrealized = (mark - new_avg) * new_qty if new_qty > 0 else 0.0
    equity = starting + new_realized + unrealized

    db.execute(
        text("UPDATE paper_portfolios SET equity_usd=:eq, updated_at=NOW() WHERE strategy_instance_id=:sid"),
        {"eq": equity, "sid": strategy_instance_id},
    )

    now_ms = int(time.time() * 1000)
    db.execute(
        text(
            """
            INSERT INTO portfolio_balances(strategy_instance_id, asset, free, locked, equity_usd, ts)
            VALUES (:sid, 'USD', :free, 0, :equity, :ts)
            """
        ),
        {"sid": strategy_instance_id, "free": equity, "equity": equity, "ts": now_ms},
    )

    db.execute(
        text(
            """
            INSERT INTO strategy_events(strategy_instance_id, event_type, payload, ts)
            VALUES (:sid, 'fill_applied', CAST(:payload AS jsonb), :ts)
            """
        ),
        {
            "sid": strategy_instance_id,
            "payload": __import__('json').dumps({
                "market": market,
                "side": side,
                "qty": qty,
                "fill_price": fill_price,
                "equity": equity,
            }),
            "ts": now_ms,
        },
    )

    db.commit()

    return {
        "qty": new_qty,
        "avg_entry_price": new_avg,
        "realized_pnl_usd": new_realized,
        "equity_usd": equity,
        "unrealized_pnl_usd": unrealized,
    }
