from sqlalchemy import text
from sqlalchemy.orm import Session


def recompute_strategy_snapshot(db: Session, strategy_instance_id: str):
    # Basic MVP metrics
    stats = db.execute(
        text(
            """
            SELECT
              COUNT(*)::int AS trade_count,
              COALESCE(SUM(CASE WHEN side='sell' AND realized_pnl_usd > 0 THEN 1 ELSE 0 END),0)::int AS wins
            FROM executions
            WHERE strategy_instance_id=:sid
            """
        ),
        {"sid": strategy_instance_id},
    ).mappings().first()

    pnl_row = db.execute(
        text(
            """
            SELECT COALESCE(realized_pnl_usd,0) AS realized
            FROM positions
            WHERE strategy_instance_id=:sid
            LIMIT 1
            """
        ),
        {"sid": strategy_instance_id},
    ).mappings().first()

    eq = db.execute(
        text("SELECT starting_equity_usd, equity_usd FROM paper_portfolios WHERE strategy_instance_id=:sid"),
        {"sid": strategy_instance_id},
    ).mappings().first()

    trade_count = int(stats["trade_count"]) if stats else 0
    wins = int(stats["wins"]) if stats else 0
    win_rate = (wins / trade_count * 100.0) if trade_count else 0.0
    realized = float(pnl_row["realized"]) if pnl_row else 0.0

    start = float(eq["starting_equity_usd"]) if eq else 10000.0
    current = float(eq["equity_usd"]) if eq else start
    dd = max(0.0, ((start - current) / start) * 100.0) if start > 0 else 0.0

    db.execute(
        text(
            """
            INSERT INTO performance_snapshots(strategy_instance_id, pnl_usd, drawdown_pct, win_rate_pct, trade_count)
            VALUES (:sid, :pnl, :dd, :wr, :tc)
            """
        ),
        {"sid": strategy_instance_id, "pnl": realized, "dd": dd, "wr": win_rate, "tc": trade_count},
    )
    db.commit()
