from fastapi import FastAPI

from app.api.routes import health, control, strategies, market, trades
from app.core.config import settings

app = FastAPI(title=settings.app_name)

app.include_router(health.router, prefix="/api")
app.include_router(control.router, prefix="/api")
app.include_router(strategies.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(trades.router, prefix="/api")


@app.get("/")
def root():
    return {"service": settings.app_name, "status": "ok"}
