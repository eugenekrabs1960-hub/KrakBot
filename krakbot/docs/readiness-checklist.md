# KrakBot Readiness Checklist (Living)

Use this as a practical pass/fail gate. Keep statuses honest.

Legend:
- [x] Pass
- [ ] Not yet pass / partial / blocked

Last updated: 2026-03-19

---

## 1) Paper Robustness

- [x] **R1. Baseline reset integrity**
  - Criteria: after `POST /api/settings/paper/reset`, cash/equity=10000, fees=0, open positions=0, trades=0.
  - Evidence: reset API returns baseline object; overview/trades/positions verified empty in latest checks.

- [ ] **R2. End-to-end cycle stability (100-cycle gate)**
  - Criteria: 100 manual cycles, 0 API errors, 0 invalid outputs, no hangs.
  - Evidence: multiple 40–60 cycle windows passed, but a formal 100-cycle clean gate not yet recorded.

- [ ] **R3. Model-path health continuity**
  - Criteria: model health remains online through full validation windows.
  - Evidence: improved, but intermittent offline/timeout events still observed during heavy runs.

- [x] **R4. Policy gate determinism**
  - Criteria: deterministic `final_action` + consistent gate checks.
  - Evidence: policy gate is authoritative; decisions consistently carry gate checks/reasons.

- [x] **R5. Execution persistence correctness**
  - Criteria: allowed trades persist and remain visible after restart.
  - Evidence: fixed `/api/trades` and `/api/positions` data-source issues; persistence verified post-restart.

- [x] **R6. Paper accounting correctness (basic)**
  - Criteria: equity/cash/fees/unrealized move coherently.
  - Evidence: `paper_account` baseline + updates are functioning and visible in overview.

- [x] **R7. Adaptive leverage safety constraints**
  - Criteria: paper-only deterministic leverage tiers; warning fallback to 1.0x; live unchanged.
  - Evidence: implemented in policy gate; observed 1.0x + 1.5x cases; no 3.0x observed.

---

## 1A) Added Gate: Paper Performance

- [ ] **P1. Fee-adjusted paper edge gate**
  - Criteria: over >= 3 independent windows (>= 60 cycles each), median fee-adjusted equity delta > 0 and not dominated by one window.
  - Evidence: recent windows are mostly neutral-to-negative after fees; gate not met.

- [ ] **P2. Trade quality gate**
  - Criteria: allowed-trade quality improves (lower low-confidence fills, stable block reasons, less churn) without collapse in opportunity capture.
  - Evidence: ongoing; mean_reversion selectivity knob surfaced but not fully evaluated across repeated windows.

---

## 2) Experiment Maturity

- [x] **E1. Low-pressure experiment guardrails enforced**
  - Criteria: defaults cycles=20/control=false + candidate cap 1 + repair off + concurrency 1 + pacing + abort-on-offline.
  - Evidence: implemented and returned in run metadata (`low_pressure_guardrails`).

- [x] **E2. One-change isolation**
  - Criteria: one `change_path` per run; runtime settings restored after run.
  - Evidence: harness design enforces one change; restoration logic in runner.

- [x] **E3. Baseline/variant reset comparability**
  - Criteria: each arm starts from clean paper reset.
  - Evidence: baseline + variant (and optional control) call paper reset service per arm.

- [x] **E4. Optional control rerun workflow**
  - Criteria: baseline -> variant -> optional control rerun supported.
  - Evidence: API + UI support present and tested.

- [x] **E5. Result completeness metadata**
  - Criteria: fills, fees, block reasons, setup/confidence distributions, classification.
  - Evidence: present in run payload summaries.

- [ ] **E6. Statistical decision discipline**
  - Criteria: no keep/reject promotion without repeated confirmation windows.
  - Evidence: process discipline still manual; not encoded as hard promote gate yet.

---

## 2A) Added Gate: LLM Operational Headroom

- [ ] **L1. Headroom gate for sustained experiments**
  - Criteria: during >= 2 consecutive 60-cycle windows, model stays online, no experiment arm aborts, and p95 cycle latency stays below agreed threshold.
  - Evidence: guardrails reduced pressure, but abort/timeout events still occur intermittently.

- [ ] **L2. Overload resilience gate**
  - Criteria: no model offline transitions during low-pressure experiment runs over a full day schedule.
  - Evidence: not yet demonstrated.

---

## 3) Hyperliquid Testnet Readiness

- [ ] **T1. Environment config completeness**
  - Criteria: testnet account + relay + auth configured and validated.
  - Evidence: path exists, but full testnet readiness evidence not yet captured in this phase.

- [ ] **T2. Testnet order lifecycle verification**
  - Criteria: submit/cancel/fill/reconcile path validated with idempotency.
  - Evidence: not fully executed/documented in current phase.

- [ ] **T3. Position/fill reconciliation gate**
  - Criteria: testnet venue state matches app state across APIs/UI.
  - Evidence: pending.

- [ ] **T4. Safety controls under testnet**
  - Criteria: live-arming guard, stop controls, and limits verified on testnet flow.
  - Evidence: pending full validation runbook execution.

- [ ] **T5. 24h testnet soak**
  - Criteria: no critical relay/execution failures in sustained testnet run.
  - Evidence: not run yet.

---

## 4) Self-Improvement Maturity

- [x] **S1. Human-in-the-loop experiment loop exists**
  - Criteria: propose -> run -> compare -> classify workflow operational.
  - Evidence: harness v1 active with persisted runs.

- [ ] **S2. Automated hypothesis generation**
  - Criteria: system proposes bounded candidate improvements autonomously.
  - Evidence: not implemented (manual only).

- [ ] **S3. Robust repeated confirmation policy**
  - Criteria: keep/reject requires repeated statistically consistent evidence across windows/regimes.
  - Evidence: partially procedural, not fully enforced.

- [ ] **S4. Regime-aware robustness checks**
  - Criteria: candidate survives multiple distinct market regimes before promotion.
  - Evidence: not formalized yet.

- [ ] **S5. Autonomous safe promotion/rollback**
  - Criteria: controlled auto-promotion with hard rollback policy.
  - Evidence: not implemented (manual only).

---

## 5) Funded-Account (Mainnet) Readiness

- [ ] **F1. Prior-stage prerequisites all green**
  - Criteria: Paper + Experiment + Testnet sections pass.
  - Evidence: not yet.

- [ ] **F2. Hard risk budget enforcement**
  - Criteria: strict funded-account limits validated in live-like drills.
  - Evidence: partial controls exist; funded validation incomplete.

- [ ] **F3. Kill-switch and rollback drills**
  - Criteria: emergency stop tested and documented.
  - Evidence: not fully demonstrated.

- [ ] **F4. Production monitoring/alerts**
  - Criteria: actionable alerts for model/relay/risk breaches.
  - Evidence: partial observability only.

- [ ] **F5. Capital ramp protocol**
  - Criteria: staged micro -> limited -> normal allocation process defined and validated.
  - Evidence: not executed.

---

## Notes

- This checklist is intentionally conservative.
- Do not mark [x] unless there is concrete evidence (API output, logs, or documented run artifact).
- Keep this file updated as gates are passed/regressed.
