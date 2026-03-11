from __future__ import annotations

import json
import time

from sqlalchemy import text
from sqlalchemy.orm import Session


def persist_hyperliquid_snapshots(db: Session, *, environment: str, account: dict | None, positions: list[dict]) -> dict:
    now_ms = int(time.time() * 1000)
    account_written = 0
    position_written = 0

    try:
        if account:
            db.execute(
                text(
                    """
                    INSERT INTO hyperliquid_account_snapshots(
                      ts, environment, equity_usd, available_margin_usd, maintenance_margin_usd, payload_json
                    )
                    VALUES (:ts, :environment, :equity_usd, :available_margin_usd, :maintenance_margin_usd, CAST(:payload_json AS jsonb))
                    """
                ),
                {
                    'ts': now_ms,
                    'environment': environment,
                    'equity_usd': float(account.get('equity_usd') or 0.0),
                    'available_margin_usd': float(account.get('available_margin_usd') or 0.0),
                    'maintenance_margin_usd': float(account.get('maintenance_margin_usd') or 0.0),
                    'payload_json': json.dumps(account),
                },
            )
            account_written = 1

        for p in positions:
            db.execute(
                text(
                    """
                    INSERT INTO hyperliquid_position_snapshots(
                      ts, environment, market, qty, avg_entry_price, realized_pnl_usd,
                      unrealized_pnl_usd, leverage, liquidation_price, payload_json
                    )
                    VALUES (
                      :ts, :environment, :market, :qty, :avg_entry_price, :realized_pnl_usd,
                      :unrealized_pnl_usd, :leverage, :liquidation_price, CAST(:payload_json AS jsonb)
                    )
                    """
                ),
                {
                    'ts': now_ms,
                    'environment': environment,
                    'market': p.get('market') or 'UNKNOWN',
                    'qty': float(p.get('qty') or 0.0),
                    'avg_entry_price': float(p.get('avg_entry_price') or 0.0),
                    'realized_pnl_usd': float(p.get('realized_pnl_usd') or 0.0),
                    'unrealized_pnl_usd': float(p.get('unrealized_pnl_usd') or 0.0),
                    'leverage': float(p.get('leverage')) if p.get('leverage') is not None else None,
                    'liquidation_price': float(p.get('liquidation_price')) if p.get('liquidation_price') is not None else None,
                    'payload_json': json.dumps(p),
                },
            )
            position_written += 1

        db.commit()
    except Exception:
        db.rollback()

    return {'ts': now_ms, 'account_written': account_written, 'position_written': position_written}


def list_latest_hyperliquid_account_snapshots(db: Session, limit: int = 20):
    try:
        rows = db.execute(
            text(
                """
                SELECT id, ts, environment, equity_usd, available_margin_usd, maintenance_margin_usd, payload_json
                FROM hyperliquid_account_snapshots
                ORDER BY id DESC
                LIMIT :limit
                """
            ),
            {'limit': max(1, min(200, int(limit)))},
        ).mappings().all()
        return [dict(r) for r in rows]
    except Exception:
        return []


def list_latest_hyperliquid_position_snapshots(db: Session, limit: int = 50):
    try:
        rows = db.execute(
            text(
                """
                SELECT id, ts, environment, market, qty, avg_entry_price, realized_pnl_usd,
                       unrealized_pnl_usd, leverage, liquidation_price, payload_json
                FROM hyperliquid_position_snapshots
                ORDER BY id DESC
                LIMIT :limit
                """
            ),
            {'limit': max(1, min(500, int(limit)))},
        ).mappings().all()
        return [dict(r) for r in rows]
    except Exception:
        return []
