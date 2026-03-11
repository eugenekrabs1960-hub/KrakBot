import json
from sqlalchemy import text
from sqlalchemy.orm import Session


def save_checkpoint(db: Session, worker_name: str, checkpoint: dict):
    db.execute(
        text(
            """
            INSERT INTO worker_checkpoints(worker_name, checkpoint, updated_at)
            VALUES (:worker_name, CAST(:checkpoint AS jsonb), CURRENT_TIMESTAMP)
            ON CONFLICT (worker_name)
            DO UPDATE SET checkpoint = EXCLUDED.checkpoint, updated_at = CURRENT_TIMESTAMP
            """
        ),
        {'worker_name': worker_name, 'checkpoint': json.dumps(checkpoint)},
    )
    db.commit()


def load_checkpoint(db: Session, worker_name: str) -> dict | None:
    row = db.execute(
        text("SELECT checkpoint FROM worker_checkpoints WHERE worker_name=:w"),
        {'w': worker_name},
    ).mappings().first()
    return row['checkpoint'] if row else None
