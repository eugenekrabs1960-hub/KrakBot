from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["relay-stub"])


class RelayReq(BaseModel):
    action: str
    symbol: str | None = None
    side: str | None = None
    notional_usd: float | None = None
    reduce_only: bool | None = None
    order_id: str | None = None
    account: str | None = None


@router.post('/live/relay-stub')
def relay_stub(req: RelayReq):
    # dev-only signer relay placeholder
    if req.action == 'place_order':
        return {
            "accepted": False,
            "status": "stub",
            "reason": "signer_not_implemented",
            "action": req.action,
            "symbol": req.symbol,
            "side": req.side,
            "notional_usd": req.notional_usd,
        }
    return {"accepted": False, "status": "stub", "reason": "not_implemented", "action": req.action}
