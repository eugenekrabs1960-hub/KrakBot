# Mode Separation Ticket Pack v1

Strict implementation tracker for separating **Trading (realtime)** vs **Research (simulation)**.

## Status legend
- [ ] Not started
- [x] Done

---

## Ordered implementation plan (must follow exactly)

1. MS-1
2. MS-2
3. MS-3
4. MS-4
5. MS-5
6. MS-6
7. MS-7
8. MS-8
9. MS-10
10. MS-9
11. MS-11
12. MS-12

---

## MS-1 — Canonical mode contract
- [ ] **Status**
- **Owner:** `TBD`
- **ETA:** `TBD`
- **Current status note:** `TBD`
- **Short description:** Add shared enums/constants for `data_mode` and related mode contract to avoid string drift.
- **Dependencies:** none
- **Files:**
  - `backend/app/core/` (new mode constants module)
  - shared schema/constants references used by backend/frontend

---

## MS-2 — Add `data_mode` to core trading/event tables
- [ ] **Status**
- **Owner:** `TBD`
- **ETA:** `TBD`
- **Current status note:** `TBD`
- **Short description:** Add required `data_mode` tagging to trading data tables and backfill existing rows to realtime mode.
- **Dependencies:** MS-1
- **Migration(s):**
  - `00ZZ_add_data_mode_to_core_event_tables.sql`
  - optional `0100_add_run_context_to_core_event_tables.sql`
- **Files:**
  - `backend/app/models/db_models.py`
  - migration SQL files

---

## MS-3 — Add `data_mode` to research table(s)
- [ ] **Status**
- **Owner:** `TBD`
- **ETA:** `TBD`
- **Current status note:** `TBD`
- **Short description:** Ensure experiment artifacts are explicitly tagged as `research_simulation`.
- **Dependencies:** MS-1
- **Migration(s):**
  - `0101_add_data_mode_to_experiment_runs.sql`
- **Files:**
  - `backend/app/models/db_models.py`
  - `backend/app/services/experiments.py`

---

## MS-4 — Trading writer tagging
- [ ] **Status**
- **Owner:** `TBD`
- **ETA:** `TBD`
- **Current status note:** `TBD`
- **Short description:** Force trading loop writes to `data_mode='trading_realtime'`.
- **Dependencies:** MS-2
- **Files:**
  - `backend/app/services/journal/writer.py`
  - `backend/app/services/decision_engine.py` (if direct writes exist)

---

## MS-5 — Research writer isolation/tagging
- [ ] **Status**
- **Owner:** `TBD`
- **ETA:** `TBD`
- **Current status note:** `TBD`
- **Short description:** Keep experiment/research writes isolated and tagged `research_simulation`.
- **Dependencies:** MS-3, MS-4
- **Files:**
  - `backend/app/services/experiments.py`
  - other research artifact writers (if any)

---

## MS-6 — Trading route filtering (mode-pure)
- [ ] **Status**
- **Owner:** `TBD`
- **ETA:** `TBD`
- **Current status note:** `TBD`
- **Short description:** Trading APIs must return only realtime-tagged rows.
- **Dependencies:** MS-2, MS-4
- **Files:**
  - `backend/app/api/routes/overview.py`
  - `backend/app/api/routes/candidates.py`
  - `backend/app/api/routes/positions.py`
  - `backend/app/api/routes/trades.py`
  - `backend/app/api/routes/decisions.py`

---

## MS-7 — Research route filtering (mode-pure)
- [ ] **Status**
- **Owner:** `TBD`
- **ETA:** `TBD`
- **Current status note:** `TBD`
- **Short description:** Research APIs must return only simulation-tagged rows.
- **Dependencies:** MS-3, MS-5
- **Files:**
  - `backend/app/api/routes/experiments.py`
  - future replay/backtest routes

---

## MS-8 — Trading synthetic fallback guard
- [ ] **Status**
- **Owner:** `TBD`
- **ETA:** `TBD`
- **Current status note:** `TBD`
- **Short description:** In Trading mode, no random/synthetic feature substitution; degrade safely instead.
- **Dependencies:** MS-6
- **Files:**
  - `backend/app/services/features/market_features.py`
  - `backend/app/services/decision_engine.py`
  - `backend/app/services/policy/gate.py` (reason routing if needed)

---

## MS-10 — Mode-aware reset semantics
- [ ] **Status**
- **Owner:** `TBD`
- **ETA:** `TBD`
- **Current status note:** `TBD`
- **Short description:** Paper reset affects trading paper state only by default; no implicit research wipe.
- **Dependencies:** MS-2, MS-3
- **Files:**
  - `backend/app/services/paper_reset.py`
  - `backend/app/api/routes/settings.py`
  - docs for reset contract

---

## MS-9 — UI mode labeling + nav separation
- [ ] **Status**
- **Owner:** `TBD`
- **ETA:** `TBD`
- **Current status note:** `TBD`
- **Short description:** Clear Trading vs Research labeling and separate nav grouping.
- **Dependencies:** MS-6, MS-7
- **Files:**
  - `frontend/src/components/Layout.tsx`
  - `frontend/src/main.tsx`
  - `frontend/src/pages/Overview.tsx`
  - `frontend/src/pages/Experiments.tsx`
  - `frontend/src/styles/app.css`

---

## MS-11 — Backend acceptance tests for separation
- [ ] **Status**
- **Owner:** `TBD`
- **ETA:** `TBD`
- **Current status note:** `TBD`
- **Short description:** Add tests proving route/data mode purity and trading no-synthetic guarantee.
- **Dependencies:** MS-6, MS-7, MS-8, MS-10
- **Files:**
  - `backend/tests/test_mode_separation_routes.py` (new)
  - `backend/tests/test_mode_separation_writers.py` (new)
  - `backend/tests/test_trading_no_synthetic_fallback.py` (new)

---

## MS-12 — CI/ops audit enforcement
- [ ] **Status**
- **Owner:** `TBD`
- **ETA:** `TBD`
- **Current status note:** `TBD`
- **Short description:** Add CI/runtime audit checks that fail on mode leakage.
- **Dependencies:** MS-11
- **Files:**
  - CI config/scripts
  - optional ops audit script under `scripts/`

---

## Notes
- Keep this document as the implementation source-of-truth for Mode Separation v1 execution.
- Do not reorder tickets unless explicitly approved.
