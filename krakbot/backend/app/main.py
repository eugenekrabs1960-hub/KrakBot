from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.adapters.marketdata_kraken import ingestor
from app.api.routes import health, control, strategies, market, trades, ws
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ingestor.start()
    try:
        yield
    finally:
        await ingestor.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(health.router, prefix="/api")
app.include_router(control.router, prefix="/api")
app.include_router(strategies.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(trades.router, prefix="/api")
app.include_router(ws.router, prefix="/api")


@app.get("/")
def root():
    return {"service": settings.app_name, "status": "ok"}
