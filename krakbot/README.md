# KrakBot AI Trading Lab (Hyperliquid-Focused)

Clean v1 implementation skeleton for an AI-assisted crypto futures lab.

## Defaults
- Tracked universe: BTC, ETH, SOL (3 coins; configurable to 3-5)
- Feature refresh cadence: 60s
- Decision cycle cadence: 300s
- Candidates sent to local model per cycle: top 2-3
- Execution mode default: paper
- No pyramiding
- Fixed small notional sizing
- Max open positions: small (paper_v1: 3)
- Live mode disabled/disarmed by default

## Backend Modules
- Canonical schemas: FeaturePacket, DecisionOutput, PolicyDecision, OutcomeLabel, ReviewReport
- Broker abstraction + PaperBroker + HyperliquidLiveBroker skeleton
- Feature + score computation skeleton
- Packet builder
- Local model adapter interface + Qwen local adapter skeleton
- Deterministic policy gate
- Journal persistence
- Outcome labeler (deterministic baseline)
- Review stub service

## API Routes
- `/api/health`
- `/api/overview`
- `/api/candidates`
- `/api/decisions/run-cycle`
- `/api/decisions/recent`
- `/api/positions`
- `/api/trades`
- `/api/settings` (GET/POST)
- `/api/execution/flatten-all`

## Run
Backend:
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8010
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```
