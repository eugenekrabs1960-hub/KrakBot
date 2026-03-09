from fastapi import APIRouter

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("")
def list_trades(limit: int = 100):
    # TODO: fetch canonical paper trades
    return {"items": [], "limit": limit}
