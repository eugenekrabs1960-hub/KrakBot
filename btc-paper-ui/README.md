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
- Phase 1 architecture tracking:
  - formal strategy registry
  - regime detection snapshot per scan
  - per-strategy metrics
  - per-regime metrics for each strategy
- Controlled learning layer:
  - scan outcome logging with strategy + regime context
  - trade lifecycle tracking including MFE/MAE
  - repeated failure pattern detection
  - compact rolling learning summary per strategy
  - shadow-mode routing recommendations with zero execution impact

## API
- `GET /api/state`
- `GET /api/history`
- `POST /api/run-scan`
- `POST /api/auto-scan` (for Pause/Resume)

## Run
### Backend (recommended for long unattended runs)
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

Notes:
- Avoid `--reload` for long unattended runs.
- The backend auto-scanner runs independently of the browser.
- State/history now persist to `backend/data/paper_state.json`, so the bot can recover after backend restarts.

### Frontend dev mode
```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173

### Frontend production-style build (lighter for long monitoring)
```bash
cd frontend
npm install
npm run build
```

Then open the dashboard from the backend server at:
```bash
http://127.0.0.1:8000/
```

This serves the built frontend from FastAPI, so you can:
- run only the backend continuously
- open/close the browser whenever you want
- avoid leaving the Vite dev server and Brave tab open for long sessions
