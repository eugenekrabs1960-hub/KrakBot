from fastapi import APIRouter

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/snapshot")
def snapshot():
    # TODO: pull from latest market cache/table
    return {
        "venue": "kraken",
        "market": "SOL/USD",
        "instrument_type": "spot",
        "last_price": None,
        "ts": None,
    }
