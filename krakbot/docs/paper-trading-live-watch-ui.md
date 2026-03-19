# Paper Trading Live-Watch UI Guide

This pass focuses on making paper trading visibly watchable in the web UI.

## What changed

### Overview = live paper-trading control room
The Overview page now shows, at a glance:
- execution mode (`paper`/`live_hyperliquid`)
- live armed/disarmed state
- trading enabled state
- model health
- last decision cycle / feature loop times
- top candidates watch table
- active paper positions table
- recent trades/fills table
- recent decisions table
- recent blocked trades table
- performance summary KPIs
- loop/reconciliation/relay health panels

### Candidates inspector
Candidates now include:
- rank + A/O/T scores
- latest action/setup/confidence
- key reasons/risks
- policy result + blocked reason
- packet context (contradiction/extension/trade_quality_prior/regime_compatibility/change summary)
- wallet summary status

### Positions monitor
Positions now include:
- coin, side, size, notional
- entry/current price (when available)
- unrealized pnl
- setup_type and opened-at metadata
- useful empty-state message if no positions

### Settings console
Settings are grouped for readability:
- Mode & Safety
- Universe
- Loop Cadence
- Model Runtime
- Risk Controls
- Experiments (info)

Safety-critical controls are visually separated.

## How to watch paper trading live

1. Open **Overview** and confirm `PAPER SAFE` badge.
2. Check **Model Health** badge/panel is online.
3. Watch KPI cards update (allowed/blocked trades, PnL, open positions).
4. Click **Run Decision Cycle** to force a cycle and observe changes immediately.
5. Use **Candidate Watch** to see what the bot currently prefers.
6. Use **Recent Decisions** and **Recent Blocked Trades** to inspect why actions happened.
7. Use **Active Paper Positions** + **Recent Trades/Fills** for paper execution visibility.

The UI auto-refreshes to keep this watch view current.

## Route/output validation summary

Validated working snapshots in this pass:
- `GET /api/overview`
- `GET /api/candidates`
- `GET /api/positions`
- `GET /api/decisions/recent`
- `GET /api/settings`

Observed from snapshots:
- mode remains `paper`, `live_armed=false`
- top candidates + recent decision traces present
- open positions and trade/fill panels populated
- performance summary fields present

## Safety confirmation

Live mode remains disarmed by default:
- `execution_mode=paper`
- `live_armed=false`

No live-default safety loosening was introduced in this pass.
