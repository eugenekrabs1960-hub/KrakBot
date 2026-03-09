# Krakbot

Multi-coin-ready crypto paper trading platform.

MVP target:
- Venue: Kraken spot
- Pair: SOL/USD
- Engine: Freqtrade (hidden behind adapter)
- UI: React + TypeScript
- Backend: Python (FastAPI)

See architecture: `../kraken_bots/KRAKBOT_MVP_ARCHITECTURE.md`

## Repo layout

- `backend/` FastAPI control plane + orchestration and domain APIs
- `frontend/` React dashboard and controls UI
- `deploy/` local docker compose and env templates

## Current status

This is an architecture-aligned scaffold (contracts + module boundaries), ready for phased implementation.
