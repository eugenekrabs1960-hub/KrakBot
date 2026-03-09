# BTC/USD 15m Paper UI (V1)

Local-only paper-trading dashboard.

## Stack
- Backend: FastAPI (`backend/main.py`)
- Frontend: React + Vite (`frontend/`)
- Chart: TradingView Lightweight Charts

## Features
- PAPER MODE badge
- BTC/USD 15m candlestick chart
- Trigger lines at 69513.0 and 68698.6
- Latest decision/regime/reason/R:R panel
- Account panel (equity, cash, positions)
- Recent scan history table
- Run Scan button
- Pause/Resume auto scan button

## API
- `GET /api/state`
- `GET /api/history`
- `POST /api/run-scan`
- `POST /api/auto-scan` (for Pause/Resume)

## Run
### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173
