from __future__ import annotations

import json
import time

from sqlalchemy import text
from sqlalchemy.orm import Session

KEY = 'live_trading_guard'


def _default():
    return {
        'enabled': False,
        'max_notional_usd_per_order': 250.0,
        'max_daily_loss_usd': 100.0,
        'allowed_agents': ['jason'],
        'updated_at_ms': int(time.time() * 1000),
    }


def get_live_trading_guard(db: Session) -> dict:
    row = db.execute(text(f"SELECT value FROM system_state WHERE key='{KEY}' LIMIT 1")).mappings().first()
    if not row:
        return {'ok': True, 'item': _default()}
    value = row.get('value')
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            value = None
    if not isinstance(value, dict):
        value = _default()
    for k, v in _default().items():
        value.setdefault(k, v)
    return {'ok': True, 'item': value}


def _upsert(db: Session, obj: dict):
    payload = json.dumps(obj)
    dialect = getattr(getattr(db, 'bind', None), 'dialect', None)
    dialect_name = getattr(dialect, 'name', '')
    if dialect_name == 'postgresql':
        db.execute(
            text(
                """
                INSERT INTO system_state(key, value, updated_at)
                VALUES ('live_trading_guard', CAST(:payload AS jsonb), CURRENT_TIMESTAMP)
                ON CONFLICT (key)
                DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                """
            ),
            {'payload': payload},
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO system_state(key, value, updated_at)
                VALUES ('live_trading_guard', :payload, CURRENT_TIMESTAMP)
                ON CONFLICT (key)
                DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                """
            ),
            {'payload': payload},
        )


def enable_live_trading_guard(
    db: Session,
    *,
    confirm_phrase: str,
    max_notional_usd_per_order: float,
    max_daily_loss_usd: float,
    allowed_agents: list[str] | None = None,
):
    if confirm_phrase != 'LIVE_ON':
        return {'ok': False, 'error': 'confirmation_required', 'required': 'LIVE_ON'}

    current = get_live_trading_guard(db)['item']
    current['enabled'] = True
    current['max_notional_usd_per_order'] = max(1.0, float(max_notional_usd_per_order))
    current['max_daily_loss_usd'] = max(1.0, float(max_daily_loss_usd))
    if allowed_agents is not None:
        current['allowed_agents'] = [str(a).strip() for a in allowed_agents if str(a).strip()]
    current['updated_at_ms'] = int(time.time() * 1000)

    _upsert(db, current)
    db.commit()
    return {'ok': True, 'item': current}


def disable_live_trading_guard(db: Session, *, confirm_phrase: str):
    if confirm_phrase != 'LIVE_OFF':
        return {'ok': False, 'error': 'confirmation_required', 'required': 'LIVE_OFF'}
    current = get_live_trading_guard(db)['item']
    current['enabled'] = False
    current['updated_at_ms'] = int(time.time() * 1000)
    _upsert(db, current)
    db.commit()
    return {'ok': True, 'item': current}


def enforce_live_trading_order_guard(db: Session, *, strategy_instance_id: str, notional_usd: float):
    cfg = get_live_trading_guard(db)['item']
    if not cfg.get('enabled'):
        return {'ok': False, 'error_code': 'live_trading_disabled', 'message': 'live trading guard is disabled'}

    allowed = set(str(x) for x in (cfg.get('allowed_agents') or []))
    if allowed and strategy_instance_id not in allowed:
        return {'ok': False, 'error_code': 'agent_not_allowed_for_live', 'message': f'{strategy_instance_id} not allowed for live trading'}

    cap = float(cfg.get('max_notional_usd_per_order') or 0)
    if cap > 0 and float(notional_usd) > cap:
        return {'ok': False, 'error_code': 'order_notional_exceeds_cap', 'message': f'notional {notional_usd:.2f} exceeds cap {cap:.2f}'}

    return {'ok': True, 'item': cfg}
