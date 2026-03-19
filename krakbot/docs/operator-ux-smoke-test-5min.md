# 5-Minute Operator UX Smoke Test

Use this quick checklist to confirm the current UI + runtime are healthy before operation.

## 0) Startup (1 min)

```bash
docker compose -f deploy/docker-compose.yml up -d postgres redis backend frontend
curl -s http://localhost:8010/api/health | jq .
```

Expected:
- services are running
- health shows `ok: true`

---

## 1) Model Health (30 sec)

UI: **Overview → Model Runtime** panel  
OR API:

```bash
curl -s http://localhost:8010/api/model/health | jq .
```

Expected:
- `ok: true`
- configured model present
- no error

---

## 2) Paper/Live Safety State (30 sec)

UI: **Overview top status strip** + **Settings → Mode & Safety**

Expected baseline:
- execution mode = `paper`
- live armed = `false`
- trading enabled = `true` (or as intentionally set)

---

## 3) Trigger One Run-Cycle (30 sec)

UI: **Overview → Run Decision Cycle** button  
OR API:

```bash
curl -s -X POST http://localhost:8010/api/decisions/run-cycle | jq '{items:(.items|length)}'
```

Expected:
- cycle returns candidate decision items
- no server errors

---

## 4) Check Candidates (45 sec)

UI: **Candidates** page

Verify:
- ranked tracked coins visible
- recommendation fields visible (action/setup/confidence)
- policy result + blocked reason fields visible
- packet context + wallet status visible

---

## 5) Check Decisions Trace (45 sec)

UI: **Decisions** page

Verify:
- rows show action/setup/confidence/policy/execution
- expand one row and inspect details (reasons/risks/policy checks/execution)

---

## 6) Check Positions (30 sec)

UI: **Positions** page

Verify either:
- open paper positions render coin/side/size/notional/setup/opened-at, or
- clear empty state appears if none

---

## 7) Confirm Live Disarmed Safety (30 sec)

UI: **Settings → Mode & Safety**
- set mode to `live_hyperliquid`
- keep `live_armed=false`
- run one cycle

Expected:
- trade-intent decisions are blocked with `block_mode_disabled`

Then return mode to `paper`.

---

## Pass Criteria

System is operator-ready if all checks pass with:
- healthy model runtime
- successful run-cycle
- readable candidates/decisions/positions pages
- clear and enforced live-disarmed safety behavior
