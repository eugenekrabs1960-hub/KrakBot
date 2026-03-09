import hashlib
import json
from sqlalchemy import text
from sqlalchemy.orm import Session


def _hash_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()


def check_or_store(
    db: Session,
    key: str,
    scope: str,
    payload: dict,
    response: dict | None = None,
):
    req_hash = _hash_payload(payload)
    row = db.execute(
        text("SELECT request_hash, response FROM idempotency_keys WHERE key=:k"),
        {"k": key},
    ).mappings().first()

    if row:
        if row['request_hash'] != req_hash:
            raise ValueError('idempotency key re-used with different payload')
        return {'replayed': True, 'response': row['response']}

    db.execute(
        text(
            """
            INSERT INTO idempotency_keys(key, scope, request_hash, response)
            VALUES (:key, :scope, :request_hash, :response::jsonb)
            """
        ),
        {
            'key': key,
            'scope': scope,
            'request_hash': req_hash,
            'response': json.dumps(response or {}),
        },
    )
    db.commit()
    return {'replayed': False, 'response': response}


def update_response(db: Session, key: str, response: dict):
    db.execute(
        text("UPDATE idempotency_keys SET response=:r::jsonb WHERE key=:k"),
        {'k': key, 'r': json.dumps(response)},
    )
    db.commit()
