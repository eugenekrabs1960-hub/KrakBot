from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.agent_decisions import list_decision_packets, record_decision_packet

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
