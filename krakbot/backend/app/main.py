from fastapi import FastAPI

from app.core.logging import setup_logging
from app.core.database import Base, engine
from app.models import db_models  # noqa: F401
from app.api.routes import health, overview, candidates, decisions, positions, trades, settings, execution, profiles

setup_logging()
Base.metadata.create_all(bind=engine)

app = FastAPI(title="KrakBot AI Trading Lab")
app.include_router(health.router, prefix="/api")
app.include_router(overview.router, prefix="/api")
app.include_router(candidates.router, prefix="/api")
app.include_router(decisions.router, prefix="/api")
app.include_router(positions.router, prefix="/api")
app.include_router(trades.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(execution.router, prefix="/api")
app.include_router(profiles.router, prefix="/api")


@app.get('/')
def root():
    return {"service": "KrakBot AI Trading Lab", "status": "ok"}
