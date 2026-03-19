# KrakBot Operator Runbook (Narrow/Practical)

Scope: boot, migration, sanity checks, paper-mode run-cycle validation, loop/reconciliation/live-safety checks.

---

## 1) Exact boot steps

From repo root (`krakbot/`):

```bash
# 1) start infra
docker compose -f deploy/docker-compose.yml up -d postgres redis

# 2) start backend (installs deps, runs migrations, starts API)
docker compose -f deploy/docker-compose.yml up -d backend

# 3) optional UI
docker compose -f deploy/docker-compose.yml up -d frontend
```

Check service state:

```bash
docker compose -f deploy/docker-compose.yml ps
```

Check backend logs:

```bash
docker compose -f deploy/docker-compose.yml logs backend --tail=120
```

---

## 2) Exact migration steps

Migrations run automatically on backend startup via:

```bash
python -m app.db.migrate
```

Manual migration run:

```bash
docker compose -f deploy/docker-compose.yml exec -T backend python -m app.db.migrate
```

Expected output:
- previously applied migrations are `skipped`
- new migrations are `applied`

---

## 3) Required / optional env vars

### Required (backend)

- `DATABASE_URL=postgresql+psycopg://krakbot:krakbot@postgres:5432/krakbot`

### Optional (live/account paths)

- `HYPERLIQUID_ACCOUNT_ADDRESS`
- `HYPERLIQUID_ORDER_RELAY_URL`
- `HYPERLIQUID_ORDER_RELAY_TOKEN`

### Notes
- Default mode is paper.
- Live remains disarmed unless explicitly armed in settings.

---

## 4) Route sanity checks

```bash
BASE=http://localhost:8010/api

curl -s $BASE/health | jq .
curl -s $BASE/settings | jq .
curl -s $BASE/overview | jq .
curl -s $BASE/loops/status | jq .
curl -s '$BASE/loops/history?limit=5' | jq .
curl -s '$BASE/reconciliation/history?limit=5' | jq .
curl -s '$BASE/execution/health' | jq .
```

You want HTTP 200 + valid JSON for all.

---

## 5) Trigger a manual paper run-cycle

```bash
curl -s -X POST http://localhost:8010/api/decisions/run-cycle | jq '{count:(.items|length), sample:.items[0]|{coin:.packet.coin, action:.decision.action, final:.policy.final_action}}'
```

Expected:
- `count` usually 2–3
- each item includes `packet`, `decision`, `policy`

---

## 6) Inspect DB write success

Quick API check:

```bash
curl -s http://localhost:8010/api/decisions/recent | jq '{packets:(.packets|length), decisions:(.decisions|length), policy:(.policy|length), execution:(.execution|length)}'
```

Direct DB check:

```bash
docker compose -f deploy/docker-compose.yml exec -T postgres psql -U krakbot -d krakbot -c "
select
  (select count(*) from feature_packets) as feature_packets,
  (select count(*) from decision_outputs) as decision_outputs,
  (select count(*) from policy_decisions) as policy_decisions,
  (select count(*) from execution_records) as execution_records,
  (select count(*) from loop_runs) as loop_runs,
  (select count(*) from reconciliation_runs) as reconciliation_runs;
"
```

---

## 7) Verify loops are running

Status endpoint:

```bash
curl -s http://localhost:8010/api/loops/status | jq .
```

History growth check:

```bash
BASE=http://localhost:8010/api
before_feature=$(curl -s $BASE/loops/history?limit=200 | jq '[.items[]|select(.loop_type=="feature")]|length')
before_decision=$(curl -s $BASE/loops/history?limit=200 | jq '[.items[]|select(.loop_type=="decision")]|length')

sleep 70

after_feature=$(curl -s $BASE/loops/history?limit=200 | jq '[.items[]|select(.loop_type=="feature")]|length')
after_decision=$(curl -s $BASE/loops/history?limit=200 | jq '[.items[]|select(.loop_type=="decision")]|length')

echo "before_feature=$before_feature before_decision=$before_decision"
echo "after_feature=$after_feature after_decision=$after_decision"
```

Expected:
- `after_feature > before_feature` (~1m cadence)
- decision cadence is slower (~5m), so may not increment in 70s

---

## 8) Verify reconciliation is working

Run reconciliation:

```bash
curl -s -X POST http://localhost:8010/api/reconciliation/run | jq .
```

Check history:

```bash
curl -s 'http://localhost:8010/api/reconciliation/history?limit=5' | jq .
```

Expected:
- POST returns `ok: true`
- history includes the new run
- drift alerts visible in `payload.drift` and `drift_count`

---

## 9) Confirm live mode is disarmed and safe

Check current mode:

```bash
curl -s http://localhost:8010/api/settings | jq '.mode'
```

Expected safe baseline:
```json
{
  "execution_mode": "paper",
  "trading_enabled": true,
  "live_armed": false,
  "emergency_stop": false
}
```

Disarmed-live safety test:

```bash
BASE=http://localhost:8010/api
orig=$(curl -s $BASE/settings)

live_disarmed=$(echo "$orig" | jq '.mode.execution_mode="live_hyperliquid" | .mode.live_armed=false')
curl -s -X POST $BASE/settings -H 'content-type: application/json' -d "$live_disarmed" > /tmp/s_live.json
curl -s -X POST $BASE/decisions/run-cycle > /tmp/cycle_live.json
jq '[.items[]|{requested:.policy.requested_action,final:.policy.final_action}]' /tmp/cycle_live.json

# restore paper
paper=$(echo "$orig" | jq '.mode.execution_mode="paper" | .mode.live_armed=false')
curl -s -X POST $BASE/settings -H 'content-type: application/json' -d "$paper" >/dev/null
```

Expected:
- trade actions in disarmed live mode are blocked with `block_mode_disabled`
- `no_trade` may still map to `downgrade_to_watch`

---

## 10) Common failure cases + quick triage

### A) Backend fails to boot with module import error
Symptom: `ModuleNotFoundError` in backend logs.

Triage:
```bash
docker compose -f deploy/docker-compose.yml logs backend --tail=200
```

Fix direction:
- check package/module naming collisions
- verify imports match file paths

---

### B) Migration issues / table mismatch
Symptom: SQL errors, undefined columns/tables.

Triage:
```bash
docker compose -f deploy/docker-compose.yml exec -T backend python -m app.db.migrate
docker compose -f deploy/docker-compose.yml exec -T postgres psql -U krakbot -d krakbot -c '\dt'
```

Fix direction:
- add/adjust migration file (don’t edit applied migration contents)
- rerun migrate

---

### C) 500 on run-cycle with JSON serialization errors
Symptom: datetime not JSON serializable.

Triage:
```bash
docker compose -f deploy/docker-compose.yml logs backend --tail=200
```

Fix direction:
- ensure payload persistence uses JSON-safe dumps

---

### D) Settings changes not affecting runtime behavior
Symptom: route says live mode but decisions still paper.

Triage:
- `GET /api/settings`
- run one cycle and inspect `policy.execution_mode`

Fix direction:
- ensure runtime settings update mutates shared state used by routes/services

---

### E) Reconciliation fails with legacy schema collisions
Symptom: undefined column errors against `positions`.

Triage:
```bash
docker compose -f deploy/docker-compose.yml logs backend --tail=200
```

Fix direction:
- use dedicated lab table (`lab_positions`) and apply migration

---

### F) Loops look stalled
Symptom: no growth in loop history.

Triage:
- `GET /api/loops/status`
- check `last_error`
- inspect backend logs

Fix direction:
- confirm backend process alive
- verify DB connectivity
- verify loop intervals in settings

---

This runbook intentionally avoids feature expansion and focuses only on stable operations.
