# Phase 2 Proof-of-Life & Validation (Paper Mode Focus)

Date: 2026-03-18/19 (America/Los_Angeles)
Branch: `main`
Scope: boot + migrations + paper-mode E2E + loop/reconciliation/overview verification + live safety checks

## 1) Required env vars

Minimum for local docker stack (`deploy/docker-compose.yml`):

- `DATABASE_URL=postgresql+psycopg://krakbot:krakbot@postgres:5432/krakbot` (backend service)

Optional (remain safe defaults when unset):
- `HYPERLIQUID_ACCOUNT_ADDRESS`
- `HYPERLIQUID_ORDER_RELAY_URL`
- `HYPERLIQUID_ORDER_RELAY_TOKEN`

## 2) Exact startup steps

From repo root (`krakbot/`):

```bash
# start dependencies
docker compose -f deploy/docker-compose.yml up -d postgres redis

# start backend (installs deps, runs migrations, starts uvicorn)
docker compose -f deploy/docker-compose.yml up -d backend

# optional frontend
docker compose -f deploy/docker-compose.yml up -d frontend
```

## 3) Exact migration steps

Migrations auto-run in backend startup command:

```bash
python -m app.db.migrate
```

Manual migration run (inside backend container):

```bash
docker compose -f deploy/docker-compose.yml exec -T backend python -m app.db.migrate
```

Expected evidence includes:
- existing migrations skipped
- `0017_ai_trading_lab_core_and_phase2c.sql` applied (first run)
- `0018_lab_positions_table.sql` applied

## 4) Successful route checks (used)

```bash
curl -s http://localhost:8010/api/health
curl -s http://localhost:8010/api/settings
curl -s http://localhost:8010/api/overview
curl -s http://localhost:8010/api/loops/status
curl -s 'http://localhost:8010/api/loops/history?limit=5'
curl -s -X POST http://localhost:8010/api/decisions/run-cycle
curl -s http://localhost:8010/api/decisions/recent
curl -s -X POST http://localhost:8010/api/reconciliation/run
curl -s 'http://localhost:8010/api/reconciliation/history?limit=5'
curl -s http://localhost:8010/api/execution/health
curl -s 'http://localhost:8010/api/execution/relay/history?limit=5'
```

## 5) One documented paper-mode run-cycle example

Run:

```bash
curl -s -X POST http://localhost:8010/api/decisions/run-cycle | jq '{n:(.items|length), sample_action:.items[0].decision.action, sample_policy:.items[0].policy.final_action}'
```

Observed example:

```json
{
  "n": 3,
  "sample_action": "short",
  "sample_policy": "block_market_conditions"
}
```

DB write verification:

```bash
docker compose -f deploy/docker-compose.yml exec -T postgres psql -U krakbot -d krakbot -c "select (select count(*) from feature_packets) as feature_packets, (select count(*) from decision_outputs) as decision_outputs, (select count(*) from policy_decisions) as policy_decisions, (select count(*) from execution_records) as execution_records, (select count(*) from loop_runs) as loop_runs, (select count(*) from reconciliation_runs) as reconciliation_runs;"
```

Observed counts after run(s):
- feature_packets: 9
- decision_outputs: 9
- policy_decisions: 9
- execution_records: 1
- loop_runs: 8
- reconciliation_runs: 1

## 6) Automatic loops verification (1m/5m)

Feature loop check:
- feature loop history count increased after ~70s wait.

Decision loop check:
- decision loop runs on 300s cadence; status/history rows persist in `loop_runs`.

## 7) Reconciliation verification

```bash
curl -s -X POST http://localhost:8010/api/reconciliation/run | jq .
```

Observed example:

```json
{
  "ok": true,
  "count": 0,
  "mode": "paper",
  "drift_count": 0,
  "alerts": [],
  "status": "ok"
}
```

History route returns persisted rows:
- `GET /api/reconciliation/history`

## 8) Overview/panels data verification

Overview now reads real panel data from:
- `GET /api/loops/status`
- `GET /api/loops/history`
- `GET /api/reconciliation/history`
- `GET /api/execution/relay/history`

Verified these routes return non-empty/valid JSON under running stack.

## 9) Live safeguards verification (default disarmed)

Default settings:
- `execution_mode: paper`
- `live_armed: false`

Explicit disarmed live test:
1. set `execution_mode=live_hyperliquid`, `live_armed=false`
2. run decision cycle
3. confirm trade actions are blocked by policy:

Observed sample:

```json
[
  {"req":"long","final":"block_mode_disabled"},
  {"req":"no_trade","final":"downgrade_to_watch"},
  {"req":"no_trade","final":"downgrade_to_watch"}
]
```

## 10) Bugs found and fixed (no new product features)

1. **Boot failure due import collision**
   - Symptom: `ModuleNotFoundError` for `app.services.reconciliation.live_reconcile`
   - Cause: file/package name collision (`services/reconciliation.py` vs `services/reconciliation/` directory)
   - Fix: moved reconciliation package code to `services/reconcile/live_reconcile.py` and updated imports.

2. **Backend DB connection target wrong in docker stack**
   - Symptom: potential backend DB mis-target (`localhost`) inside container
   - Fix: set backend env in compose: `DATABASE_URL=...@postgres:5432/...`

3. **Run-cycle 500 on JSON payload writes**
   - Symptom: `TypeError: Object of type datetime is not JSON serializable`
   - Cause: raw `model_dump()`/payload dictionaries with datetime fields persisted into JSON columns
   - Fix: use `model_dump(mode='json')` and normalize execution payload datetime.

4. **Reconciliation 500 due legacy table collision**
   - Symptom: `column positions.symbol does not exist`
   - Cause: existing legacy `positions` table schema differed from new model
   - Fix: renamed lab table to `lab_positions` in ORM + added migration `0018_lab_positions_table.sql`.

5. **Mode changes not propagating reliably across modules**
   - Symptom: policy still evaluated as `paper` after switching settings to live
   - Cause: settings route replaced runtime object instead of mutating in place
   - Fix: changed settings update to mutate existing `runtime_settings` fields in place.

---
Validation scope completed with no unrelated new product features.
