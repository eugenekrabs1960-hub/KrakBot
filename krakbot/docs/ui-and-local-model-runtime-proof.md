# UI Usability + Local Model Runtime Proof (Validation Phase)

Date: 2026-03-19  
Branch: `main`

Scope adhered:
- no new external data sources
- no new product feature families
- focused on UI usability wiring and local model runtime reliability

---

## 1) Exact startup steps

From repo root (`krakbot/`):

```bash
# infra
docker compose -f deploy/docker-compose.yml up -d postgres redis

# backend (includes migrations + uvicorn)
docker compose -f deploy/docker-compose.yml up -d backend

# frontend
docker compose -f deploy/docker-compose.yml up -d frontend
```

Check backend logs:

```bash
docker compose -f deploy/docker-compose.yml logs backend --tail=200
```

---

## 2) Exact local model config/env needed

Configured via backend settings:

- `local_model_name=Qwen3.5-9B`
- `local_model_base_url=http://10.50.0.30:8000`
- `local_model_timeout_sec=20`
- `local_model_api_key=` (optional, empty for open local endpoint)

Model health endpoint:

- `GET /api/model/health`

Observed sample:

```json
{
  "ok": true,
  "base_url": "http://10.50.0.30:8000",
  "configured_model": "Qwen3.5-9B",
  "reachable_models": ["Qwen3.5-9B-Q4_K_M.gguf"],
  "latency_ms": 1,
  "error": null
}
```

---

## 3) Confirmed working UI pages/routes

### Overview
- Loads mode/safety indicators and real loop/reconciliation/relay values.
- Shows wallet summaries and model runtime health panel.

### Candidates
- Shows ranked candidates + opportunity/tradability + wallet summary columns.

### Decisions
- Shows decision outputs table, policy results table, execution outcomes table.

### Positions
- Shows paper positions with qty + entry/unrealized where available.

### Settings
- Reads and writes runtime settings and updates behavior.

### Route checks (all 200)
- `/api/overview`
- `/api/candidates`
- `/api/decisions/recent`
- `/api/positions`
- `/api/settings`
- `/api/loops/status`
- `/api/reconciliation/history`
- `/api/execution/relay/history`
- `/api/wallets/summary`
- `/api/model/health`

---

## 4) Confirmed working local-model path

### Adapter/runtime path
- `QwenLocalAdapter` now dispatches to local OpenAI-compatible endpoint (`/v1/chat/completions`).
- Strict JSON extraction + Pydantic validation.
- Deterministic fallback remains for resilience.

### Repeated run-cycle validation
20 consecutive `POST /api/decisions/run-cycle` calls:

```json
{
  "runs": 20,
  "errors": 0,
  "invalid_decisions": 0,
  "latency_ms": {
    "min": 1414.71,
    "p50": 1586.67,
    "mean": 1631.36,
    "p95": 2130.87,
    "max": 2135.77
  }
}
```

Interpretation:
- stable for 5-minute cadence (runtime call latencies ~1.4s–2.1s)
- no run-cycle crashes observed in repeated test
- DecisionOutput validity remained intact

### Repair-path proof
- `output_repair` path smoke-tested in backend container with intentionally incomplete decision payload.
- Successfully produced schema-valid repaired object.

---

## 5) Bugs fixed in this phase

1. **Local model not truly used**
   - Fixed by wiring actual endpoint dispatch in `QwenLocalAdapter`.

2. **Validation/repair not enforced in runner flow**
   - Fixed in `analyst_runner` with post-adapter validation + optional repair pass.

3. **UI usability gaps**
   - Decisions page now readable (decisions/policy/execution tables).
   - Candidates page now includes wallet columns.
   - Positions page includes mode/entry/unrealized columns.
   - Overview now includes model runtime health panel and clearer safety status.
   - Added frontend periodic refresh (20s) for operator practicality.

---

## 6) Route/output summaries proving working state

- `GET /api/model/health` returns reachable model list.
- `POST /api/decisions/run-cycle` repeatedly returns success and schema-valid outputs.
- `GET /api/wallets/summary` returns tracked-coin summaries.
- `GET /api/overview` includes `wallet_summaries` and mode/safety values.

---

## Conclusion

Current web UI is operational and practical for operator use, and the local analyst model runtime is reachable and stable in repeated end-to-end runs at acceptable latency for 5-minute cadence.
