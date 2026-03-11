import json

from sqlalchemy import text
from sqlalchemy.orm import Session

DEFAULT_VENUE = 'paper'


def _normalize_venue(venue: str | None) -> str:
    v = str(venue or DEFAULT_VENUE)
    return v if v in {'paper', 'hyperliquid'} else DEFAULT_VENUE


def get_default_execution_venue(db: Session) -> str:
    row = db.execute(
        text("SELECT value FROM system_state WHERE key='execution_preferences' LIMIT 1")
    ).mappings().first()
    if not row:
        return DEFAULT_VENUE

    value = row.get('value')
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return DEFAULT_VENUE

    if not isinstance(value, dict):
        return DEFAULT_VENUE
    return _normalize_venue(value.get('default_venue'))


def set_default_execution_venue(db: Session, venue: str) -> str:
    venue = _normalize_venue(venue)
    value_json = json.dumps({'default_venue': venue})

    dialect = getattr(getattr(db, 'bind', None), 'dialect', None)
    dialect_name = getattr(dialect, 'name', '')

    if dialect_name == 'postgresql':
        db.execute(
            text(
                """
                INSERT INTO system_state(key, value, updated_at)
                VALUES ('execution_preferences', CAST(:value_json AS jsonb), CURRENT_TIMESTAMP)
                ON CONFLICT (key)
                DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                """
            ),
            {'value_json': value_json},
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO system_state(key, value, updated_at)
                VALUES ('execution_preferences', :value_json, CURRENT_TIMESTAMP)
                ON CONFLICT (key)
                DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                """
            ),
            {'value_json': value_json},
        )

    db.commit()
    return venue
