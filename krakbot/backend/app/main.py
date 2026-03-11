from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.adapters.marketdata_kraken import ingestor
from app.api.routes import health, control, strategies, market, trades, ws, reliability, market_registry, eif, wallet_intel, execution
from app.core.config import settings
from app.services.live_paper_test_mode import live_paper_test_mode
from app.services.wallet_intel_scheduler import wallet_intel_scheduler
from app.services.hyperliquid_market_scheduler import hyperliquid_market_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ingestor.start()
    await live_paper_test_mode.start()
    await wallet_intel_scheduler.start()
    await hyperliquid_market_scheduler.start()
    try:
        yield
    finally:
        await hyperliquid_market_scheduler.stop()
        await wallet_intel_scheduler.stop()
        await live_paper_test_mode.stop()
        await ingestor.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(health.router, prefix="/api")
app.include_router(control.router, prefix="/api")
app.include_router(strategies.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(trades.router, prefix="/api")
app.include_router(ws.router, prefix="/api")
app.include_router(reliability.router, prefix="/api")
app.include_router(market_registry.router, prefix="/api")
app.include_router(eif.router, prefix="/api")
app.include_router(wallet_intel.router, prefix="/api")
app.include_router(execution.router, prefix="/api")


@app.get("/")
def root():
    return {"service": settings.app_name, "status": "ok"}
