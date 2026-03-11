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


def compute_latest_hyperliquid_risk_snapshot(db: Session):
    account_rows = list_latest_hyperliquid_account_snapshots(db, limit=1)
    position_rows = list_latest_hyperliquid_position_snapshots(db, limit=500)

    account = account_rows[0] if account_rows else None
    if not position_rows:
        return {
            'ok': True,
            'as_of_ts': account.get('ts') if account else None,
            'margin_utilization_pct': 0.0,
            'total_notional_usd': 0.0,
            'position_concentration_pct': 0.0,
            'liq_distance_bands': {'high_risk_lt_10pct': 0, 'medium_10_to_25pct': 0, 'low_gt_25pct': 0},
            'positions_count': 0,
        }

    latest_ts = max(int(r.get('ts') or 0) for r in position_rows)
    latest_positions = [r for r in position_rows if int(r.get('ts') or 0) == latest_ts]

    notionals = [abs(float(r.get('qty') or 0.0) * float(r.get('avg_entry_price') or 0.0)) for r in latest_positions]
    total_notional = sum(notionals)
    top_notional = max(notionals) if notionals else 0.0
    concentration = (top_notional / total_notional * 100.0) if total_notional > 0 else 0.0

    high = med = low = 0
    for r in latest_positions:
        entry = float(r.get('avg_entry_price') or 0.0)
        liq = r.get('liquidation_price')
        if not entry or liq is None:
            low += 1
            continue
        dist_pct = abs(entry - float(liq)) / abs(entry) * 100.0
        if dist_pct < 10:
            high += 1
        elif dist_pct < 25:
            med += 1
        else:
            low += 1

    equity = float((account or {}).get('equity_usd') or 0.0)
    maint = float((account or {}).get('maintenance_margin_usd') or 0.0)
    margin_util = (maint / equity * 100.0) if equity > 0 else 0.0

    return {
        'ok': True,
        'as_of_ts': max(latest_ts, int((account or {}).get('ts') or 0)),
        'margin_utilization_pct': margin_util,
        'total_notional_usd': total_notional,
        'position_concentration_pct': concentration,
        'liq_distance_bands': {
            'high_risk_lt_10pct': high,
            'medium_10_to_25pct': med,
            'low_gt_25pct': low,
        },
        'positions_count': len(latest_positions),
    }
