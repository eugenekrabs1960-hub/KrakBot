import json
from sqlalchemy import text
from sqlalchemy.orm import Session


def save_checkpoint(db: Session, worker_name: str, checkpoint: dict):
    payload = json.dumps(checkpoint)
    dialect = getattr(getattr(db, 'bind', None), 'dialect', None)
    dialect_name = getattr(dialect, 'name', '')

    if dialect_name == 'postgresql':
        db.execute(
            text(
                """
                INSERT INTO worker_checkpoints(worker_name, checkpoint, updated_at)
                VALUES (:worker_name, CAST(:checkpoint AS jsonb), CURRENT_TIMESTAMP)
                ON CONFLICT (worker_name)
                DO UPDATE SET checkpoint = EXCLUDED.checkpoint, updated_at = CURRENT_TIMESTAMP
                """
            ),
            {'worker_name': worker_name, 'checkpoint': payload},
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO worker_checkpoints(worker_name, checkpoint, updated_at)
                VALUES (:worker_name, :checkpoint, CURRENT_TIMESTAMP)
                ON CONFLICT (worker_name)
                DO UPDATE SET checkpoint = excluded.checkpoint, updated_at = CURRENT_TIMESTAMP
                """
            ),
            {'worker_name': worker_name, 'checkpoint': payload},
        )

    db.commit()


def load_checkpoint(db: Session, worker_name: str) -> dict | None:
    row = db.execute(
        text("SELECT checkpoint FROM worker_checkpoints WHERE worker_name=:w"),
        {'w': worker_name},
    ).mappings().first()
    if not row:
        return None

    value = row['checkpoint']
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return None
    return value if isinstance(value, dict) else None
