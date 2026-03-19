# Paper Micro-Calibration Report: Portfolio Limits Saturation

Date: 2026-03-18/19  
Branch: `main`  
Scope: narrow paper-mode calibration only (no new product features, no live safety relaxation)

## Objective
Diagnose `block_risk` saturation and make the smallest paper-only adjustment to improve evaluation throughput while preserving discipline.

---

## 1) Root-cause diagnosis of `block_risk`

Dataset windows: controlled 30-cycle runs (~90 decisions each), paper mode, live disarmed, decision loop slowed during measurement.

### Before micro-calibration
- `block_risk_total`: **42**
- `block_risk_portfolio_limits`: **42**
- `block_risk_risk_environment`: **0**

Portfolio sub-check failures inside `portfolio_limits`:
- `max_open_positions_failed`: **42**
- `max_total_notional_failed`: **0**
- `direction_not_allowed_failed`: **0**

**Conclusion:** majority of block_risk outcomes are from **max_open_positions saturation**.

---

## 2) Bottleneck determination

Requested bottleneck breakdown:

- max_open_positions ✅ **Primary bottleneck**
- max_total_notional ❌ Not observed as a blocker in this run
- per-trade notional sizing ❌ Not observed as direct blocker
- hold duration / position overlap ✅ **Contributing mechanism** (positions persist/overlap in paper, causing slot saturation)
- per-coin exposure rules ❌ Not implemented in current policy path

---

## 3) Exact paper-only parameter/logic changes

### Change A: paper material-position threshold for slot counting
File: `backend/app/core/config.py`
- Added: `paper_material_position_qty_threshold = 0.75`

### Change B: use threshold when computing `current_open_positions` (paper only)
File: `backend/app/services/decision_engine.py`
- Before (paper): counted any non-zero qty (`abs(qty) > 1e-9`)
- After (paper): count only material positions (`abs(qty) >= 0.75`)
- Live mode logic unchanged.

### Supporting diagnostics hardening (already in this narrow phase)
File: `backend/app/services/policy/gate.py`
- Added explicit reason tags for portfolio-limit failures:
  - `max_open_positions_failed`
  - `max_total_notional_failed`
  - `direction_not_allowed`
- Added practical estimated total-notional check for gate observability.

### No live safety changes
- `live_v1` untouched
- default mode remains paper
- live remains disarmed by default

---

## 4) Before/after metrics (focused window)

### BEFORE (micro calibration)
Actions:
- long: 38
- short: 35
- no_trade: 17

Gate outcomes:
- allow_trade: 4
- downgrade_to_watch: 17
- block_market_conditions: 27
- block_risk: 42

Most common block reasons:
- portfolio_limits: 42
- market_quality: 27

Trade-through:
- requested trades: 73
- allowed: 4
- trade-through rate: **5.48%**

---

### AFTER (micro calibration)
Actions:
- long: 34
- short: 40
- no_trade: 16

Gate outcomes:
- allow_trade: 8
- downgrade_to_watch: 16
- block_market_conditions: 36
- block_risk: 30

Most common block reasons:
- market_quality: 36
- portfolio_limits: 30

Trade-through:
- requested trades: 74
- allowed: 8
- trade-through rate: **10.81%**

---

## 5) Discipline check after adjustment

- Output validity remained intact:
  - reasons<2: 0
  - risks<1: 0
  - trade without invalidation: 0
- System still blocks heavily on market quality and remaining portfolio limits.
- Behavior moved from overly passive to moderately more active in paper testing.

---

## 6) Recommendation: stable paper profile going forward

Recommended stable paper setup:
1. Keep current paper thresholded slot counting (`paper_material_position_qty_threshold=0.75`).
2. Keep `PAPER_V1.max_open_positions=3` (unchanged) for discipline.
3. Keep live defaults and safeguards unchanged.

Rationale:
- doubles evaluation throughput (trade-through ~5.5% -> ~10.8%) without removing portfolio discipline entirely.
- avoids the overly aggressive jump seen when simply increasing `max_open_positions` to 4.

---

## Notes
- This phase intentionally avoided new product features.
- Next tuning can remain narrow by monitoring `market_quality` blockers, now that portfolio saturation is reduced.
