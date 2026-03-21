from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logging import setup_logging
from app.core.database import Base, engine
from app.models import db_models  # noqa: F401
from app.api.routes import health, overview, candidates, decisions, positions, trades, settings, execution, profiles, wallets, model_runtime, experiments, autonomy, autonomy_core
from app.api.routes_live import loops, reconciliation, relay_stub
from app.services.loops.scheduler import loop_scheduler
from app.services.autonomy.auto_apply_worker import autonomy_auto_apply_worker
from app.core.config import settings as app_settings

setup_logging()
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if app_settings.auto_loops_enabled:
        await loop_scheduler.start()
    if app_settings.autonomy_auto_apply_enabled:
        await autonomy_auto_apply_worker.start()
    try:
        yield
    finally:
        if app_settings.auto_loops_enabled:
            await loop_scheduler.stop()
        if app_settings.autonomy_auto_apply_enabled:
            await autonomy_auto_apply_worker.stop()


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
app.include_router(experiments.router, prefix="/api")
app.include_router(autonomy.router, prefix="/api")
app.include_router(autonomy_core.router, prefix="/api")
app.include_router(loops.router, prefix="/api")
app.include_router(reconciliation.router, prefix="/api")
app.include_router(relay_stub.router, prefix="/api")


@app.get('/')
def root():
    return {"service": "KrakBot AI Trading Lab", "status": "ok"}
