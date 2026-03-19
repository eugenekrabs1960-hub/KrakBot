from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logging import setup_logging
from app.core.database import Base, engine
from app.models import db_models  # noqa: F401
from app.api.routes import health, overview, candidates, decisions, positions, trades, settings, execution, profiles, wallets, model_runtime
from app.api.routes_live import loops, reconciliation, relay_stub
from app.services.loops.scheduler import loop_scheduler

setup_logging()
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await loop_scheduler.start()
    try:
        yield
    finally:
        await loop_scheduler.stop()


app = FastAPI(title="KrakBot AI Trading Lab", lifespan=lifespan)
app.include_router(health.router, prefix="/api")
app.include_router(overview.router, prefix="/api")
app.include_router(candidates.router, prefix="/api")
app.include_router(decisions.router, prefix="/api")
app.include_router(positions.router, prefix="/api")
app.include_router(trades.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(execution.router, prefix="/api")
app.include_router(profiles.router, prefix="/api")
app.include_router(wallets.router, prefix="/api")
app.include_router(model_runtime.router, prefix="/api")
app.include_router(loops.router, prefix="/api")
app.include_router(reconciliation.router, prefix="/api")
app.include_router(relay_stub.router, prefix="/api")


@app.get('/')
def root():
    return {"service": "KrakBot AI Trading Lab", "status": "ok"}
