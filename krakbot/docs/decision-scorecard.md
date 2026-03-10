# Custom vs LEAN Decision Scorecard

Use this scorecard to decide whether to keep the current custom engine, adopt LEAN as a research sidecar, or migrate more deeply.

## How to use

1. Run a 2-week parallel evaluation (custom current path + LEAN research sidecar).
2. Score each criterion 1-5 for both options.
3. Multiply by weight and sum totals.
4. Check must-pass gates.
5. Decide using the rubric at the end.

Scoring scale:
- **5** = excellent, proven by evidence
- **4** = good, minor gaps
- **3** = acceptable, mixed
- **2** = weak
- **1** = poor/unreliable

---

## A) Weighted scorecard (blank)

| Category | Weight | Custom Score (1-5) | LEAN Score (1-5) | Custom Weighted | LEAN Weighted | Evidence / Notes |
|---|---:|---:|---:|---:|---:|---|
| Research iteration speed (idea -> tested result) | 15 |  |  |  |  |  |
| Backtest rigor (controls, diagnostics, reproducibility) | 15 |  |  |  |  |  |
| Backtest <-> live-paper consistency | 15 |  |  |  |  |  |
| Execution correctness confidence | 10 |  |  |  |  |  |
| Data pipeline trustworthiness | 10 |  |  |  |  |  |
| Integration complexity/friction (lower friction = higher score) | 10 |  |  |  |  |  |
| Control-plane fit (works with existing UI/ops model) | 10 |  |  |  |  |  |
| Operational maintainability (debugging, monitoring, ownership) | 10 |  |  |  |  |  |
| Future extensibility (multi-coin/futures/model workflows) | 5 |  |  |  |  |  |
| Total cost of change (time + risk) | 10 |  |  |  |  |  |
| **TOTAL** | **100** |  |  |  |  |  |

Formula:
- `Custom Weighted = Custom Score * Weight`
- `LEAN Weighted = LEAN Score * Weight`
- Max total per option = 500

---

## B) Must-pass gates (binary)

If LEAN fails any gate, do not migrate core yet.

- [ ] No momentum break: adoption does not freeze roadmap > 2 weeks
- [ ] Comparable metrics: apples-to-apples comparison is possible
- [ ] Operational clarity: team can debug and operate LEAN confidently
- [ ] Integration boundary clear: no control-plane architecture thrash
- [ ] Measured benefit proven (not hypothetical)

---

## C) Evidence checklist

Collect this before final scoring:

### Velocity
- Median time from strategy change -> evaluated result
- Number of successful iterations/day

### Quality
- Backtest report richness (drawdown, turnover, trade distribution, etc.)
- Reproducibility: identical inputs produce identical outputs

### Fidelity
- Drift between backtest assumptions and live-paper behavior
- Fill-price realism checks

### Cost
- Migration effort estimate (person-days)
- New failure modes introduced
- Long-term maintenance burden

---

## D) Decision rubric

### Outcome 1: Stay custom now, use LEAN as research sidecar
Choose if:
- Custom total >= LEAN total, or
- LEAN fails any must-pass gate

### Outcome 2: Hybrid medium-term
Choose if:
- LEAN clearly improves research rigor/velocity,
- but integration risk/cost is still high

### Outcome 3: Migrate strategy/execution core toward LEAN
Choose only if:
- LEAN total is >= 15% higher than custom,
- all must-pass gates pass,
- migration can be staged without roadmap freeze

---

## E) Baseline snapshot (current known state)

Date: 2026-03-09

Current custom platform (already verified):
- FastAPI backend + React/TS frontend
- Postgres storage
- Kraken live market-data ingestion
- Paper execution tied to observed market trades
- Multiple isolated paper portfolios per strategy
- Control plane + monitoring UI
- Strict no-random pricing rule for paper fills
- Live paper test loop available (config-gated)

Known gaps / caveats:
- Auto test loop is currently throughput-oriented; not yet strategy-effectiveness grade
- Integration tests include some conditional skips depending on live market preconditions
- Still local/dev-style ops; production-grade observability hardening pending

Initial directional recommendation (pending scored eval):
- Keep custom execution/control plane now
- Evaluate LEAN in parallel for research/backtesting only

---

## F) 2-week evaluation cadence (suggested)

Week 1:
- Normalize comparable metrics between custom and LEAN
- Implement one representative strategy in LEAN sidecar
- Collect baseline velocity + quality + fidelity data

Week 2:
- Run side-by-side evaluations on same market windows
- Score weighted table
- Apply must-pass gates
- Make final decision with documented rationale
