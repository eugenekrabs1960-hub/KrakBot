from fastapi import APIRouter

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("")
def list_strategies():
    # TODO: fetch from strategy_instances + performance snapshots
    return []
