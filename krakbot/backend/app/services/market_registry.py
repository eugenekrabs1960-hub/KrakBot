import uuid
from sqlalchemy import text
from sqlalchemy.orm import Session


def list_markets(db: Session, enabled_only: bool = False):
    sql = """
      SELECT id, venue, symbol, base_asset, quote_asset, instrument_type, enabled, metadata
      FROM market_registry
    """
    if enabled_only:
        sql += " WHERE enabled = TRUE"
    sql += " ORDER BY symbol"
    rows = db.execute(text(sql)).mappings().all()
    return [dict(r) for r in rows]


def create_market(db: Session, payload: dict):
    market_id = f"mkt_{uuid.uuid4().hex[:12]}"
    db.execute(
        text(
            """
            INSERT INTO market_registry(id, venue, symbol, base_asset, quote_asset, instrument_type, enabled, metadata)
            VALUES (:id, :venue, :symbol, :base_asset, :quote_asset, :instrument_type, :enabled, CAST(:metadata AS jsonb))
            """
        ),
        {
            'id': market_id,
            'venue': payload['venue'],
            'symbol': payload['symbol'],
            'base_asset': payload['base_asset'],
            'quote_asset': payload.get('quote_asset', 'USD'),
            'instrument_type': payload.get('instrument_type', 'spot'),
            'enabled': payload.get('enabled', False),
            'metadata': __import__('json').dumps(payload.get('metadata', {})),
        },
    )
    db.commit()
    return {'market_id': market_id}


def toggle_market(db: Session, market_id: str, enabled: bool):
    db.execute(
        text("UPDATE market_registry SET enabled=:enabled, updated_at=NOW() WHERE id=:id"),
        {'enabled': enabled, 'id': market_id},
    )
    db.commit()


def assign_market(db: Session, strategy_instance_id: str, market_id: str, enabled: bool = True):
    db.execute(
        text(
            """
            INSERT INTO strategy_markets(strategy_instance_id, market_id, enabled)
            VALUES (:sid, :mid, :enabled)
            ON CONFLICT (strategy_instance_id, market_id)
            DO UPDATE SET enabled = EXCLUDED.enabled
            """
        ),
        {'sid': strategy_instance_id, 'mid': market_id, 'enabled': enabled},
    )
    db.commit()
