from __future__ import annotations

import json
import time

from sqlalchemy import text
from sqlalchemy.orm import Session


def record_decision_packet(
    db: Session,
    *,
    agent_id: str,
    symbol: str,
    action: str,
    confidence: float | None,
    rationale: str | None,
    context: dict,
    risk: dict,
    execution: dict,
    outcome: dict | None = None,
):
    ts = int(time.time() * 1000)
    payload = {
        'ts': ts,
        'agent_id': agent_id,
        'symbol': symbol,
        'action': action,
        'confidence': confidence,
        'rationale': rationale,
        'context_json': json.dumps(context or {}),
        'risk_json': json.dumps(risk or {}),
        'execution_json': json.dumps(execution or {}),
        'outcome_json': json.dumps(outcome or {}),
    }

    dialect = getattr(getattr(db, 'bind', None), 'dialect', None)
    dialect_name = getattr(dialect, 'name', '')
    if dialect_name == 'postgresql':
        db.execute(
            text(
                """
                INSERT INTO agent_decision_packets(
                  ts, agent_id, symbol, action, confidence, rationale,
                  context_json, risk_json, execution_json, outcome_json
                )
                VALUES (
                  :ts, :agent_id, :symbol, :action, :confidence, :rationale,
                  CAST(:context_json AS jsonb), CAST(:risk_json AS jsonb), CAST(:execution_json AS jsonb), CAST(:outcome_json AS jsonb)
                )
                """
            ),
            payload,
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO agent_decision_packets(
                  ts, agent_id, symbol, action, confidence, rationale,
                  context_json, risk_json, execution_json, outcome_json
                )
                VALUES (
                  :ts, :agent_id, :symbol, :action, :confidence, :rationale,
                  :context_json, :risk_json, :execution_json, :outcome_json
                )
                """
            ),
            payload,
        )
    db.commit()
    return {'ok': True, 'ts': ts}


def list_decision_packets(db: Session, limit: int = 100, agent_id: str | None = None, symbol: str | None = None):
    where = ['1=1']
    params = {'limit': max(1, min(1000, int(limit)))}
    if agent_id:
        where.append('agent_id=:agent_id')
        params['agent_id'] = agent_id
    if symbol:
        where.append('symbol=:symbol')
        params['symbol'] = symbol

    rows = db.execute(
        text(
            f"""
            SELECT id, ts, agent_id, symbol, action, confidence, rationale,
                   context_json, risk_json, execution_json, outcome_json
            FROM agent_decision_packets
            WHERE {' AND '.join(where)}
            ORDER BY id DESC
            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()
    items = []
    for r in rows:
        d = dict(r)
        for k in ('context_json', 'risk_json', 'execution_json', 'outcome_json'):
            v = d.get(k)
            if isinstance(v, str):
                try:
                    d[k] = json.loads(v)
                except Exception:
                    pass
        items.append(d)
    return {'ok': True, 'items': items}
