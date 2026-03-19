from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from fastapi import Query

from app.lab.contracts import ExecutionMode
from app.lab.engine import ENGINE, profiles_snapshot
from app.lab.profiles import RISK_PROFILES
from app.lab.state import STATE

router = APIRouter(tags=["trading-lab"])


class RunCycleRequest(BaseModel):
    symbol: str = "BTC"


class ModeUpdateRequest(BaseModel):
    execution_mode: ExecutionMode
    live_armed: bool = False
    risk_profile_id: str | None = None


@router.get("/lab/health")
def lab_health() -> dict:
    return {
        "ok": True,
        "service": "krakbot-ai-trading-lab",
        "mode": STATE.mode.model_dump(),
        "log_count": len(STATE.logs),
    }


@router.get("/lab/profiles")
def get_profiles() -> dict:
    return profiles_snapshot()


@router.get("/lab/state")
def get_state() -> dict:
    return {
        "mode": STATE.mode.model_dump(),
        "paper_positions": STATE.paper_positions,
        "price_history_points": len(STATE.price_history),
        "log_count": len(STATE.logs),
    }


@router.post("/lab/mode")
def update_mode(req: ModeUpdateRequest) -> dict:
    STATE.mode.execution_mode = req.execution_mode
    STATE.mode.live_armed = req.live_armed
    if req.risk_profile_id:
        if req.risk_profile_id not in RISK_PROFILES:
            return {"ok": False, "error": "unknown_risk_profile_id"}
        STATE.mode.risk_profile_id = req.risk_profile_id
    return {"ok": True, "mode": STATE.mode.model_dump()}


@router.post("/lab/cycle/run-once")
def run_cycle(req: RunCycleRequest) -> dict:
    cycle = ENGINE.run_cycle(symbol=req.symbol)
    return cycle.model_dump()


@router.get("/lab/logs")
def get_logs(limit: int = Query(default=20, ge=1, le=200)) -> dict:
    return {"items": STATE.logs[-limit:]}


@router.post("/lab/paper/reset")
def reset_paper() -> dict:
    STATE.paper_positions.clear()
    return {"ok": True}
