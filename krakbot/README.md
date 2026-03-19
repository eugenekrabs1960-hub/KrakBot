# KrakBot — AI Trading Lab (Hyperliquid-focused)

This repo is now redirected into a **focused AI-assisted crypto futures trading lab**.

## Product Direction

KrakBot is not a broad dashboard anymore. v1 is intentionally narrow:

1. Ingest market/account snapshots
2. Compute deterministic features
3. Compute deterministic meta-scores
4. Build model-neutral `FeaturePacket`
5. Send packet to local analyst model adapter (Qwen3.5-9B baseline)
6. Receive strict `DecisionOutput`
7. Apply deterministic policy gate
8. Route execution to paper or live Hyperliquid broker backend
9. Log full cycle for later labeling/review

## Architecture Principles Enforced in v1

- **Model-neutral contracts** (`FeaturePacket`, `DecisionOutput`, `GateResult`)
- **Single system for paper + live** (two broker backends, same orchestrator)
- **Deterministic safety gate** between model and execution
- **Local model as analyst** (proposal only, no direct execution control)
- **Versioned profiles** for risk/model/score settings

## Current v1 Scope

The current first working version is a vertical slice with:

- FastAPI backend decision loop
- In-memory runtime store (for quick iteration)
- Paper broker execution path
- Live Hyperliquid broker contract stub
- Minimal web UI to run cycles, switch modes, and inspect logs

## Run

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8010
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## API (v1)

- `GET /api/lab/health`
- `GET /api/lab/profiles`
- `GET /api/lab/state`
- `POST /api/lab/mode`
- `POST /api/lab/cycle/run-once`
- `GET /api/lab/logs?limit=20`
- `POST /api/lab/paper/reset`

## Next Steps

- Replace market/account stubs with real Hyperliquid data adapters
- Wire live Hyperliquid signed execution into live broker adapter
- Persist packets/decisions/execution logs in DB
- Add labeling pipeline and review queue
- Add supervisor loop and model portability adapters
