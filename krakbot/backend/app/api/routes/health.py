from fastapi import APIRouter

from app.adapters.marketdata_kraken import ingestor

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"ok": True, "market_ingestor_running": ingestor._running}
