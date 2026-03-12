from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.agent_decisions import list_decision_packets, record_decision_packet
from app.core.config import settings
from app.services.jason_agent import execute_jason_decision, get_jason_state, list_jason_trades, run_jason_once, run_jason_rule_based_once, get_risk_profile, set_risk_profile, export_benchmark_reasoning_rows, export_benchmark_reasoning_csv, get_tradable_universe, set_tradable_universe, get_portfolio_gate, set_portfolio_gate, get_correlation_buckets, set_correlation_buckets

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
    decision_source: str = Field(default='oauth_gpt54')


class JasonRiskProfileRequest(BaseModel):
    profile: str = Field(default='balanced')


class JasonUniverseRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)


class JasonPortfolioGateRequest(BaseModel):
    config: dict = Field(default_factory=dict)


class JasonBucketsRequest(BaseModel):
    buckets: dict = Field(default_factory=dict)


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


@router.post('/jason/run-rule-once')
def jason_run_rule_once(db: Session = Depends(get_db)):
    try:
        return run_jason_rule_based_once(db)
    except Exception as exc:
        return {'ok': False, 'error': str(exc)[:300]}


@router.get('/jason/loop-status')
def jason_loop_status():
    return {'ok': True, 'enabled': settings.jason_loop_enabled, 'interval_sec': settings.jason_loop_interval_sec}


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
        decision_source=payload.decision_source,
    )


@router.post('/jason/execute-oauth-decision')
def jason_execute_oauth_decision(payload: JasonDecisionRequest, db: Session = Depends(get_db)):
    return execute_jason_decision(
        db,
        action=payload.action,
        symbol=payload.symbol,
        leverage=payload.leverage,
        allocation_pct=payload.allocation_pct,
        confidence=payload.confidence,
        rationale=payload.rationale,
        decision_source='oauth_gpt54',
    )


@router.get('/jason/risk-profile')
def jason_risk_profile(db: Session = Depends(get_db)):
    return get_risk_profile(db)


@router.post('/jason/risk-profile')
def jason_set_risk_profile(payload: JasonRiskProfileRequest, db: Session = Depends(get_db)):
    return set_risk_profile(db, payload.profile)


@router.get('/jason/state')
def jason_state(db: Session = Depends(get_db)):
    return get_jason_state(db)


@router.get('/jason/trades')
def jason_trades(limit: int = 100, db: Session = Depends(get_db)):
    return list_jason_trades(db, limit=limit)


@router.get('/jason/benchmark-reasoning')
def jason_benchmark_reasoning(limit: int = 500, db: Session = Depends(get_db)):
    return export_benchmark_reasoning_rows(db, limit=limit)


@router.post('/jason/benchmark-reasoning/export-job')
def jason_benchmark_reasoning_export_job(limit: int = 5000, db: Session = Depends(get_db)):
    return export_benchmark_reasoning_csv(db, limit=limit)


@router.get('/jason/universe')
def jason_universe(db: Session = Depends(get_db)):
    return get_tradable_universe(db)


@router.post('/jason/universe')
def jason_set_universe(payload: JasonUniverseRequest, db: Session = Depends(get_db)):
    return set_tradable_universe(db, payload.symbols)


@router.get('/jason/portfolio-gate')
def jason_portfolio_gate(db: Session = Depends(get_db)):
    return get_portfolio_gate(db)


@router.post('/jason/portfolio-gate')
def jason_set_portfolio_gate(payload: JasonPortfolioGateRequest, db: Session = Depends(get_db)):
    return set_portfolio_gate(db, payload.config)


@router.get('/jason/correlation-buckets')
def jason_correlation_buckets(db: Session = Depends(get_db)):
    return get_correlation_buckets(db)


@router.post('/jason/correlation-buckets')
def jason_set_correlation_buckets(payload: JasonBucketsRequest, db: Session = Depends(get_db)):
    return set_correlation_buckets(db, payload.buckets)
