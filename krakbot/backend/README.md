# Krakbot Backend

FastAPI control plane scaffold.

## Run locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

## Contract direction
- Canonical domain APIs (engine-neutral)
- Freqtrade integration only via adapter module
- Per-strategy isolated paper portfolios
