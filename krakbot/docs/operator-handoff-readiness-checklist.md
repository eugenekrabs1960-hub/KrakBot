# Operator Handoff Readiness Checklist (Final Pre-Signal Pass)

Date: 2026-03-19  
Branch: `main`

Scope: final operator usability/readiness checklist only. No new product features.

---

## A) Startup checklist

From repo root (`krakbot/`):

```bash
# infra
docker compose -f deploy/docker-compose.yml up -d postgres redis

# backend
docker compose -f deploy/docker-compose.yml up -d backend

# frontend
docker compose -f deploy/docker-compose.yml up -d frontend
```

Quick sanity:

```bash
docker compose -f deploy/docker-compose.yml ps
curl -s http://localhost:8010/api/health | jq .
```

Expected:
- backend and frontend running
- health returns `ok: true`

---

## B) UI click-path checklist (end-to-end)

1. Open web UI.
2. **Overview**
   - verify mode badge shows paper / live armed state
   - verify model runtime panel has `ok: true`
   - verify wallet panel has 3 tracked coin summaries
   - verify loop/recon/relay panels render values
3. **Candidates**
   - verify 3 ranked candidates shown
   - verify wallet columns (bias/conviction) render
4. **Decisions**
   - verify decision table rows load
   - verify policy table rows load
   - verify execution table rows load
5. **Positions**
   - verify paper positions table renders current qty/entry fields
6. **Settings**
   - verify read current settings
   - change one safe field (e.g. decision interval), save, confirm reflected on reload

---

## C) Route checklist (main operator workflows)

All expected HTTP 200:

- `GET /api/health`
- `GET /api/model/health`
- `GET /api/settings`
- `GET /api/overview`
- `GET /api/candidates`
- `GET /api/positions`
- `GET /api/decisions/recent`
- `POST /api/decisions/run-cycle`
- `GET /api/loops/status`
- `GET /api/reconciliation/history?limit=3`
- `GET /api/execution/relay/history?limit=3`
- `GET /api/wallets/summary`

Verified snapshot in this pass:
- health/model/settings/overview/candidates/decisions/positions: working
- run-cycle: returns items with packet/decision/policy/execution
- loop/recon/relay/wallet endpoints: working

---

## D) Local model health verification

Run:

```bash
curl -s http://localhost:8010/api/model/health | jq .
```

Expected fields:
- `ok: true`
- `configured_model: Qwen3.5-9B`
- `reachable_models` contains local model id
- latency present

Observed in this pass:
- `ok: true`
- base URL reachable
- model list returned

---

## E) Paper run-cycle verification

Run:

```bash
curl -s -X POST http://localhost:8010/api/decisions/run-cycle | jq '{n:(.items|length), sample:.items[0]|{symbol:.packet.symbol, action:.decision.action, final:.policy.final_action}}'
```

Expected:
- `n` around top candidate count (typically 2-3)
- each item includes packet+decision+policy (+execution if allowed)

Observed in this pass:
- `cycle_items: 3`
- sample item included wallet_summary in packet optional_signals

---

## F) Settings verification

Run:

```bash
curl -s http://localhost:8010/api/settings | jq '.mode,.loop'
```

Expected baseline:
- paper mode
- live_armed false

Save test:
- POST modified settings bundle
- GET settings and confirm persisted runtime values

---

## G) Live-disarmed safety verification

Procedure:
1. set `execution_mode=live_hyperliquid`
2. keep `live_armed=false`
3. run one decision cycle

Expected:
- trade-intent actions (`long`/`short`) blocked with `block_mode_disabled`

Observed in this pass:
- 3/3 trade-intent items blocked as `block_mode_disabled`

---

## H) Common operator mistakes + quick checks

1. **UI stale state confusion**
   - click run-cycle then refresh (or wait auto-refresh)
   - confirm with `/api/decisions/recent`

2. **Model endpoint unreachable**
   - check `/api/model/health`
   - if `ok=false`, verify local model server and base URL

3. **Settings changed but behavior seems unchanged**
   - re-fetch `/api/settings`
   - run one manual cycle and inspect policy execution_mode in result

4. **Expecting live execution while disarmed**
   - verify mode/armed in settings and overview
   - disarmed live should block trade intents by design

5. **No wallet panel data**
   - run 1-2 manual cycles
   - check `/api/wallets/summary`

---

## Final readiness verdict

System is operator-ready for current phase:
- UI pages are functional and practical
- local model runtime path is healthy
- paper run-cycle path works repeatedly
- safety-state verification is straightforward
- core operator workflows have route-level checks with expected outputs
