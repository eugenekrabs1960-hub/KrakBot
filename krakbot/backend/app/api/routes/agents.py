from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.agent_decisions import list_decision_packets, record_decision_packet
from app.services.jason_agent import execute_jason_decision, get_jason_state, list_jason_trades, run_jason_once

router = APIRouter(prefix='/agents', tags=['agents'])


class DecisionPacketRequest(BaseModel):
    agent_id: str
    symbol: str
    action: str
    confidence: float | None = None
    rationale: str | None = None
    context: dict = {}
    risk: dict = {}
    execution: dict = {}
    outcome: dict = {}


class JasonDecisionRequest(BaseModel):
    action: str = Field(default='hold')
    symbol: str = Field(default='BTC')
    leverage: float = Field(default=1.0)
    allocation_pct: float = Field(default=0.0)
    confidence: float = Field(default=0.0)
    rationale: str = Field(default='No rationale provided')


@router.post('/decision-packets')
def create_decision_packet(payload: DecisionPacketRequest, db: Session = Depends(get_db)):
    return record_decision_packet(
        db,
        agent_id=payload.agent_id,
        symbol=payload.symbol,
        action=payload.action,
        confidence=payload.confidence,
        rationale=payload.rationale,
        context=payload.context,
        risk=payload.risk,
        execution=payload.execution,
        outcome=payload.outcome,
    )


@router.get('/decision-packets')
def get_decision_packets(limit: int = 100, agent_id: str | None = None, symbol: str | None = None, db: Session = Depends(get_db)):
    return list_decision_packets(db, limit=limit, agent_id=agent_id, symbol=symbol)


@router.post('/jason/run-once')
def jason_run_once(db: Session = Depends(get_db)):
    try:
        return run_jason_once(db)
    except Exception as exc:
        return {'ok': False, 'error': str(exc)[:300]}


@router.post('/jason/execute-decision')
def jason_execute_decision(payload: JasonDecisionRequest, db: Session = Depends(get_db)):
    return execute_jason_decision(
        db,
        action=payload.action,
        symbol=payload.symbol,
        leverage=payload.leverage,
        allocation_pct=payload.allocation_pct,
        confidence=payload.confidence,
        rationale=payload.rationale,
    )


@router.get('/jason/state')
def jason_state(db: Session = Depends(get_db)):
    return get_jason_state(db)


@router.get('/jason/trades')
def jason_trades(limit: int = 100, db: Session = Depends(get_db)):
    return list_jason_trades(db, limit=limit)
