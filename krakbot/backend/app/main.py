from fastapi import FastAPI

from app.api.routes_lab.lab import router as lab_router

app = FastAPI(title="KrakBot AI Trading Lab")
app.include_router(lab_router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {
        "service": "KrakBot AI Trading Lab",
        "status": "ok",
        "focus": "Hyperliquid futures + model-assisted deterministic execution",
    }
