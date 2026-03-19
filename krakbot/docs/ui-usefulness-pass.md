# UI Usefulness Pass (Operator-Focused)

Date: 2026-03-19  
Branch: `main`  
Scope: usability/observability improvements only for existing system.

## What was improved

### 1) Overview / Control Room

Overview now answers at-a-glance:
- execution mode
- live armed/disarmed
- trading enabled state
- model runtime health
- last decision cycle / last feature loop
- open position count
- tracked coins
- recent allowed trades
- recent blocked trades + dominant block reasons
- loop/reconciliation/relay state in readable panels
- wallet summary status

Files:
- `frontend/src/pages/Overview.tsx`
- `backend/app/api/routes/overview.py`

### 2) Candidate Inspector

Candidates now include operator-useful context per coin:
- rank + coin/symbol
- A/O/T score trio
- latest model recommendation (action/setup/confidence)
- key reasons/risks (compact)
- latest policy result + blocked reason
- packet context: contradiction / extension / trade_quality_prior / regime_compatibility / change_summary
- wallet summary status

Files:
- `frontend/src/pages/Candidates.tsx`
- `backend/app/api/routes/candidates.py`

### 3) Decision Trace

Decisions now behave as a usable log:
- row-level timestamp, coin, action, setup, confidence, policy result, execution status, short reason summary
- expandable detail row per decision with:
  - decision context (thesis/reasons/risks/invalidation/targets)
  - policy checks + block reasons
  - execution payload

Files:
- `frontend/src/pages/Decisions.tsx`

### 4) Position/Trade Monitor

Positions now show:
- coin, side, size, notional, entry, unrealized PnL, mode, related setup_type, opened_at
- clear empty-state guidance when no positions exist

Files:
- `frontend/src/pages/Positions.tsx`
- `backend/app/api/routes/positions.py`

### 5) Settings Usability

Settings are now grouped and labeled by operator intent:
- Mode & Safety (danger highlighted)
- Universe
- Loop Cadence
- Model Runtime
- Risk Controls (danger highlighted)
- Experiments (informational)

Safety-critical toggles are visually distinct.

Files:
- `frontend/src/components/SettingsForms.tsx`
- `frontend/src/pages/Settings.tsx`

### 6) Refresh/polish

- frontend auto-refresh every 20s retained and applied to improved pages
- labels/headings are operator-oriented

Files:
- `frontend/src/main.tsx`

---

## Route-oriented validation summary (working snapshots)

All endpoints below returned HTTP 200 during validation:

- `GET /api/overview`
- `GET /api/candidates`
- `GET /api/decisions/recent`
- `GET /api/positions`
- `GET /api/settings`
- `GET /api/model/health`
- `GET /api/loops/status`
- `GET /api/reconciliation/history`
- `GET /api/execution/relay/history`
- `GET /api/wallets/summary`
- `POST /api/decisions/run-cycle`

Snapshot highlights from validation:

- Overview:
  - `mode.execution_mode = paper`
  - `live_armed = false`
  - `open_positions_count = 2`
  - `recent_allowed_trades = 10`
  - `recent_blocked_trades = 10`
  - `dominant_block_reasons = { market_quality: 8, portfolio_limits: 2 }`
  - `wallet_summaries = 3`

- Candidates:
  - 3 tracked candidates shown
  - each includes `latest_decision`, `latest_policy`, `packet_context`, `wallet_summary`

- Decisions:
  - decisions/policy/execution arrays populated
  - row sample includes model action + policy result + execution status

- Positions:
  - populated with side/notional/setup/opened_at

- Settings:
  - grouped values returned and editable

- Model health:
  - `ok=true`, model reachable at configured local endpoint

- Live-disarmed safety remains clear and unchanged.

---

## Non-goals respected

- no new signal pipelines
- no strategy identity changes
- no threshold loosening
- no live default changes
- no backend product-scope expansion beyond UI observability shaping
