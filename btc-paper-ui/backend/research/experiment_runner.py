#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

BASE_DIR = Path(__file__).resolve().parent
PROGRAM_FILE = BASE_DIR / "experiment_program.md"
SURFACE_FILE = BASE_DIR / "experiment_surface.json"
RUNS_FILE = BASE_DIR / "experiment_runs.jsonl"

KRAKEN_BASELINE_MODE = "btc_15m_conservative"
KRAKEN_LEARNER_MODE = "btc_15m_conservative_netedge_v1"
HYPERLIQUID_BASELINE_MODE = "hl_15m_trend_follow"
HYPERLIQUID_LEARNER_MODE = "hl_15m_trend_follow_momo_gate_v1"

ALLOWED_KRAKEN_MODES = {KRAKEN_LEARNER_MODE}
ALLOWED_HL_MODES = {HYPERLIQUID_LEARNER_MODE}

HL_REGIME_ACTIONABILITY_FAMILY = "hl_regime_actionability_limit_test_v1"
HL_REGIME_ACTIONABILITY_PARAMS = [
    "actionable_confidence_min",
    "neutral_regime_participation_allow",
    "min_regime_strength_for_probe_entries",
    "max_probe_risk_fraction",
    "leverage_cap_during_probe_phase",
    "leverage_escalation_gate_enabled",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def append_run(entry: dict[str, Any]) -> None:
    RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RUNS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def fetch_state(api_base: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    with httpx.Client(timeout=20.0) as c:
        kr = c.get(f"{api_base}/api/state").json()
        hl = c.get(f"{api_base}/api/hyperliquid/state").json()
        try:
            news = c.get(f"{api_base}/api/news/context").json()
        except Exception:
            news = {}
    return kr, hl, news


def classify_kraken_mode(mode_key: str, mode_state: dict[str, Any]) -> dict[str, Any]:
    cmp_verdict = mode_state.get("comparator_verdict") or "INSUFFICIENT_DATA"
    review = (mode_state.get("mode_review_recommendation") or {}).get("recommended_status") or "insufficient_data"
    sm = mode_state.get("strategy_metrics") or {}
    sample = int(sm.get("sample_size", 0) or 0)
    expectancy = float(sm.get("expectancy", 0.0) or 0.0)
    fee_drag = float(sm.get("fee_drag_pct", 0.0) or 0.0)

    if cmp_verdict in {"PROMOTE_CANDIDATE", "KEEP_TESTING"}:
        keep_discard = "keep"
    elif cmp_verdict == "PROBATION":
        keep_discard = "probation"
    elif cmp_verdict == "DISCARD_CANDIDATE":
        keep_discard = "discard_watch"
    else:
        keep_discard = "inconclusive"

    return {
        "domain": "kraken",
        "mode": mode_key,
        "comparator_verdict": cmp_verdict,
        "mode_review": review,
        "sample_size": sample,
        "expectancy_net": expectancy,
        "fee_drag_pct": fee_drag,
        "keep_discard": keep_discard,
    }


def classify_hl_mode(mode_key: str, hl_state: dict[str, Any]) -> dict[str, Any]:
    overall = ((hl_state.get("metrics") or {}).get("strategy_overall") or {}).get(mode_key, {})
    sample = int(overall.get("sample_closed", 0) or 0)
    expectancy = float(overall.get("expectancy_net", 0.0) or 0.0)
    fee_drag = float(overall.get("fee_drag_pct", 0.0) or 0.0)

    book = (hl_state.get("books") or {}).get(mode_key, {})
    hist = (book.get("history") or [])[-120:]
    latest = ((book.get("latest") or {}).get("decision") or {})
    latest_reason = str(latest.get("reason") or "")

    wait_reasons: dict[str, int] = {}
    waits = 0
    actionable = 0
    non_actionable_waits = 0
    for r in hist:
        d = (r.get("decision") or r)
        st = d.get("status")
        reason = str(d.get("reason") or "")
        if st == "WAIT":
            waits += 1
            wait_reasons[reason] = wait_reasons.get(reason, 0) + 1
            if "regime not actionable" in reason.lower():
                non_actionable_waits += 1
        elif st in {"PROPOSE_TRADE", "PAPER_TRADE_OPEN"}:
            actionable += 1

    dominant_reason = max(wait_reasons.items(), key=lambda x: x[1])[0] if wait_reasons else latest_reason
    wait_ratio = (waits / max(1, len(hist))) if hist else 0.0
    action_ratio = (actionable / max(1, len(hist))) if hist else 0.0
    non_actionable_wait_ratio = (non_actionable_waits / max(1, len(hist))) if hist else 0.0

    if sample < 20:
        keep_discard = "inconclusive"
    elif expectancy > 0 and fee_drag <= 120:
        keep_discard = "keep"
    elif expectancy <= 0:
        keep_discard = "probation"
    else:
        keep_discard = "inconclusive"

    return {
        "domain": "hyperliquid",
        "mode": mode_key,
        "comparator_verdict": "N/A",
        "mode_review": "n/a",
        "sample_size": sample,
        "expectancy_net": expectancy,
        "fee_drag_pct": fee_drag,
        "keep_discard": keep_discard,
        "latest_reason": latest_reason,
        "dominant_wait_reason": dominant_reason,
        "wait_ratio": round(wait_ratio, 4),
        "action_ratio": round(action_ratio, 4),
        "non_actionable_wait_ratio": round(non_actionable_wait_ratio, 4),
    }


def _default_limit_test_config() -> dict[str, Any]:
    return {
        "family": HL_REGIME_ACTIONABILITY_FAMILY,
        "enabled": True,
        "phase": "phase_1_probe_only",
        "phase_1_min_observation_runs": 2,
        "same_blocker_rotate_after": 3,
        "goals": [
            "unblock_regime_actionability",
            "reduce_wait_from_non_actionable_regime",
            "validate_probe_phase_before_escalation",
        ],
        "thresholds": {
            "min_non_actionable_wait_ratio_improvement": 0.10,
            "min_actionable_ratio_improvement": 0.08,
            "max_expectancy_net_drop": 0.03,
            "max_fee_drag_pct_increase": 20.0,
            "max_blocker_persistence_delta": 0,
        },
        "rollback": {
            "expectancy_net_drop": 0.05,
            "fee_drag_pct_increase": 30.0,
            "non_actionable_wait_ratio_regression": 0.07,
            "actionable_ratio_drop": 0.05,
        },
        "bounds": {
            "actionable_confidence_min": {"min": 0.45, "max": 0.70, "step": 0.03, "default": 0.58},
            "neutral_regime_participation_allow": {"default": False},
            "min_regime_strength_for_probe_entries": {"min": 0.35, "max": 0.65, "step": 0.05, "default": 0.50},
            "max_probe_risk_fraction": {"min": 0.20, "max": 0.60, "step": 0.10, "default": 0.35},
            "leverage_cap_during_probe_phase": {"min": 1.5, "max": 4.0, "step": 0.5, "default": 3.0},
            "leverage_escalation_gate_enabled": {"default": False},
        },
    }


def _limit_test_config(surface: dict[str, Any]) -> dict[str, Any]:
    cfg = _default_limit_test_config()
    user = surface.get("autonomy_config", {}).get("hyperliquid_limit_test", {}) if isinstance(surface, dict) else {}
    if not isinstance(user, dict):
        return cfg

    merged = dict(cfg)
    merged.update({k: v for k, v in user.items() if k in {"enabled", "family", "phase", "phase_1_min_observation_runs", "same_blocker_rotate_after"}})

    t = dict(cfg.get("thresholds", {}))
    if isinstance(user.get("thresholds"), dict):
        t.update(user.get("thresholds") or {})
    merged["thresholds"] = t

    rb = dict(cfg.get("rollback", {}))
    if isinstance(user.get("rollback"), dict):
        rb.update(user.get("rollback") or {})
    merged["rollback"] = rb

    b = dict(cfg.get("bounds", {}))
    if isinstance(user.get("bounds"), dict):
        for k, v in user.get("bounds", {}).items():
            if isinstance(v, dict):
                cur = dict(b.get(k, {}))
                cur.update(v)
                b[k] = cur
    merged["bounds"] = b

    goals = user.get("goals")
    if isinstance(goals, list) and goals:
        merged["goals"] = [str(g) for g in goals]

    return merged


def _load_recent_runs(limit: int = 200) -> list[dict[str, Any]]:
    if not RUNS_FILE.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with RUNS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if isinstance(r, dict):
                        rows.append(r)
                except Exception:
                    continue
    except Exception:
        return []
    return rows[-limit:]


def _extract_family_memory(runs: list[dict[str, Any]], family: str, mode: str) -> dict[str, Any]:
    tests = []
    for r in runs:
        m = r.get("mutation") or {}
        if not isinstance(m, dict):
            continue
        if m.get("domain") != "hyperliquid" or m.get("mode") != mode:
            continue
        if str(m.get("limit_test_family") or "") != family:
            continue
        tests.append(r)

    blocker = None
    blocker_persist = 0
    seen_deltas: set[str] = set()
    for tr in reversed(tests):
        mut = tr.get("mutation") or {}
        sig = f"{mut.get('param')}:{mut.get('new')}"
        seen_deltas.add(sig)
        analysis = next((a for a in (tr.get("analyses") or []) if a.get("mode") == mode), None)
        dom = str((analysis or {}).get("dominant_wait_reason") or "")
        if blocker is None:
            blocker = dom
            blocker_persist = 1
        elif dom == blocker and dom:
            blocker_persist += 1
        else:
            break

    return {
        "tests_in_family": len(tests),
        "same_blocker_persistence": blocker_persist,
        "same_blocker_text": blocker or "",
        "seen_deltas": sorted(seen_deltas),
    }


def _phase_metrics(runs: list[dict[str, Any]], mode: str, family: str) -> dict[str, Any]:
    family_runs = [r for r in runs if str((r.get("mutation") or {}).get("limit_test_family") or "") == family]
    mode_analyses = []
    for r in family_runs:
        a = next((x for x in (r.get("analyses") or []) if x.get("mode") == mode), None)
        if a:
            mode_analyses.append(a)
    if not mode_analyses:
        return {"obs": 0}

    first = mode_analyses[0]
    last = mode_analyses[-1]
    return {
        "obs": len(mode_analyses),
        "non_actionable_wait_ratio_improvement": round(float(first.get("non_actionable_wait_ratio", 0.0)) - float(last.get("non_actionable_wait_ratio", 0.0)), 4),
        "actionable_ratio_improvement": round(float(last.get("action_ratio", 0.0)) - float(first.get("action_ratio", 0.0)), 4),
        "expectancy_net_delta": round(float(last.get("expectancy_net", 0.0)) - float(first.get("expectancy_net", 0.0)), 4),
        "fee_drag_pct_delta": round(float(last.get("fee_drag_pct", 0.0)) - float(first.get("fee_drag_pct", 0.0)), 4),
    }


def _passes_escalation(metrics: dict[str, Any], cfg: dict[str, Any]) -> bool:
    if int(metrics.get("obs", 0) or 0) < int(cfg.get("phase_1_min_observation_runs", 3) or 3):
        return False
    th = cfg.get("thresholds", {}) if isinstance(cfg.get("thresholds"), dict) else {}
    return (
        float(metrics.get("non_actionable_wait_ratio_improvement", 0.0)) >= float(th.get("min_non_actionable_wait_ratio_improvement", 0.10))
        and float(metrics.get("actionable_ratio_improvement", 0.0)) >= float(th.get("min_actionable_ratio_improvement", 0.08))
        and float(metrics.get("expectancy_net_delta", 0.0)) >= -float(th.get("max_expectancy_net_drop", 0.03))
        and float(metrics.get("fee_drag_pct_delta", 0.0)) <= float(th.get("max_fee_drag_pct_increase", 20.0))
    )


def _force_escalation_when_stuck(target: dict[str, Any], metrics: dict[str, Any], news_context: dict[str, Any] | None = None) -> bool:
    """
    Bounded fast-path: if phase-1 keeps seeing the same non-actionable blocker with minimal action,
    allow phase-2 escalation earlier (still paper-only and rollback-protected).
    """
    obs = int(metrics.get("obs", 0) or 0)
    if obs < 2:
        return False

    non_actionable_wait_ratio = float(target.get("non_actionable_wait_ratio", 0.0) or 0.0)
    action_ratio = float(target.get("action_ratio", 0.0) or 0.0)
    dom_reason = str(target.get("dominant_wait_reason") or "").lower()

    if "regime not actionable" not in dom_reason:
        return False
    if non_actionable_wait_ratio < 0.80 or action_ratio > 0.12:
        return False

    news = news_context or {}
    news_risk = str(news.get("news_risk", "low"))
    news_conf = str(news.get("source_confidence", "low"))
    if news_risk == "high" and news_conf in {"medium", "high"}:
        return False

    return True


def _needs_rollback(metrics: dict[str, Any], cfg: dict[str, Any]) -> bool:
    rb = cfg.get("rollback", {}) if isinstance(cfg.get("rollback"), dict) else {}
    return (
        float(metrics.get("expectancy_net_delta", 0.0)) < -float(rb.get("expectancy_net_drop", 0.05))
        or float(metrics.get("fee_drag_pct_delta", 0.0)) > float(rb.get("fee_drag_pct_increase", 30.0))
        or float(metrics.get("non_actionable_wait_ratio_improvement", 0.0)) < -float(rb.get("non_actionable_wait_ratio_regression", 0.07))
        or float(metrics.get("actionable_ratio_improvement", 0.0)) < -float(rb.get("actionable_ratio_drop", 0.05))
    )


def _choose_goal(cfg: dict[str, Any], phase: str) -> str:
    goals = [str(g) for g in (cfg.get("goals") or [])]
    if phase == "phase_1_probe_only" and "validate_probe_phase_before_escalation" in goals:
        return "validate_probe_phase_before_escalation"
    if "reduce_wait_from_non_actionable_regime" in goals:
        return "reduce_wait_from_non_actionable_regime"
    return goals[0] if goals else "unblock_regime_actionability"


def _bounded_step(current: float, spec: dict[str, Any], direction: str = "down") -> float:
    lo = float(spec.get("min", current))
    hi = float(spec.get("max", current))
    step = float(spec.get("step", 0.01) or 0.01)
    if direction == "down":
        return round(max(lo, current - step), 4)
    return round(min(hi, current + step), 4)


def propose_mutation(surface: dict[str, Any], analyses: list[dict[str, Any]], news_context: dict[str, Any] | None = None) -> dict[str, Any] | None:
    candidates = [a for a in analyses if a["keep_discard"] in {"inconclusive", "probation", "discard_watch"}]
    if not candidates:
        return None
    priority = {"discard_watch": 0, "probation": 1, "inconclusive": 2}
    domain_pri = {"hyperliquid": 0, "kraken": 1}
    candidates.sort(key=lambda x: (domain_pri.get(x.get("domain"), 9), priority.get(x["keep_discard"], 9), x["sample_size"], x["expectancy_net"]))
    target = candidates[0]

    news_context = news_context or {}
    risk = str(news_context.get("news_risk", "low"))
    conf = str(news_context.get("source_confidence", "low"))
    cautious = risk == "high" or (risk == "medium" and conf in {"medium", "high"})

    if target["domain"] == "kraken" and target["mode"] in ALLOWED_KRAKEN_MODES:
        mode = target["mode"]
        s = surface.setdefault("kraken_overrides", {}).setdefault(mode, {})
        current_rr = float(s.get("rr_min", 1.5))
        rr_step = 0.02 if cautious else 0.05
        new_rr = round(max(1.20, current_rr - rr_step), 2)
        if new_rr == current_rr:
            return None
        return {
            "domain": "kraken",
            "mode": mode,
            "param": "rr_min",
            "old": current_rr,
            "new": new_rr,
            "reason": "small-step exploration under fixed evaluator",
            "context_note": "news_cautious_step" if cautious else "news_normal_step",
            "mutation_mode": "normal_adaptive",
            "limit_test_goal": None,
        }

    if target["domain"] == "hyperliquid" and target["mode"] in ALLOWED_HL_MODES:
        mode = target["mode"]
        s = surface.setdefault("hyperliquid_overrides", {}).setdefault(mode, {})

        cfg = _limit_test_config(surface)
        if not bool(cfg.get("enabled", True)):
            return None

        recent = _load_recent_runs(limit=250)
        fam_memory = _extract_family_memory(recent, HL_REGIME_ACTIONABILITY_FAMILY, mode)
        phase_metrics = _phase_metrics(recent, mode, HL_REGIME_ACTIONABILITY_FAMILY)

        phase = str(cfg.get("phase", "phase_1_probe_only"))
        if phase == "phase_1_probe_only" and (
            _passes_escalation(phase_metrics, cfg)
            or _force_escalation_when_stuck(target, phase_metrics, news_context=news_context)
        ):
            phase = "phase_2_escalation"
        elif phase == "phase_2_escalation" and _needs_rollback(phase_metrics, cfg):
            phase = "phase_3_rollback"

        dom_reason = str(target.get("dominant_wait_reason") or "")
        non_actionable_wait_ratio = float(target.get("non_actionable_wait_ratio", 0.0) or 0.0)
        if "regime not actionable" not in dom_reason.lower() and non_actionable_wait_ratio < 0.40:
            return None

        seen_deltas = set(fam_memory.get("seen_deltas", []))
        rotate_after = int(cfg.get("same_blocker_rotate_after", 3) or 3)
        blocker_persist = int(fam_memory.get("same_blocker_persistence", 0) or 0)
        rotate_family_hypothesis = blocker_persist >= rotate_after

        bounds = cfg.get("bounds", {}) if isinstance(cfg.get("bounds"), dict) else {}
        goal = _choose_goal(cfg, phase)

        candidate_mutations: list[dict[str, Any]] = []

        if phase == "phase_3_rollback":
            old = bool(s.get("neutral_regime_participation_allow", bounds.get("neutral_regime_participation_allow", {}).get("default", False)))
            if old:
                candidate_mutations.append({"param": "neutral_regime_participation_allow", "old": old, "new": False, "reason": "rollback: disable neutral probe participation"})
            old = float(s.get("max_probe_risk_fraction", bounds.get("max_probe_risk_fraction", {}).get("default", 0.35)) or 0.35)
            new = _bounded_step(old, bounds.get("max_probe_risk_fraction", {}), direction="down")
            if new != old:
                candidate_mutations.append({"param": "max_probe_risk_fraction", "old": old, "new": new, "reason": "rollback: reduce probe risk fraction"})
            old = float(s.get("leverage_cap_during_probe_phase", bounds.get("leverage_cap_during_probe_phase", {}).get("default", 3.0)) or 3.0)
            new = _bounded_step(old, bounds.get("leverage_cap_during_probe_phase", {}), direction="down")
            if new != old:
                candidate_mutations.append({"param": "leverage_cap_during_probe_phase", "old": old, "new": new, "reason": "rollback: lower probe leverage cap"})
            old = bool(s.get("leverage_escalation_gate_enabled", bounds.get("leverage_escalation_gate_enabled", {}).get("default", False)))
            if old:
                candidate_mutations.append({"param": "leverage_escalation_gate_enabled", "old": old, "new": False, "reason": "rollback: disable leverage escalation gate"})
        elif phase == "phase_2_escalation":
            old = bool(s.get("leverage_escalation_gate_enabled", bounds.get("leverage_escalation_gate_enabled", {}).get("default", False)))
            if not old:
                candidate_mutations.append({"param": "leverage_escalation_gate_enabled", "old": old, "new": True, "reason": "phase-2 escalation: enable leverage escalation gate"})
            old = float(s.get("leverage_cap_during_probe_phase", bounds.get("leverage_cap_during_probe_phase", {}).get("default", 3.0)) or 3.0)
            new = _bounded_step(old, bounds.get("leverage_cap_during_probe_phase", {}), direction="up")
            if new != old:
                candidate_mutations.append({"param": "leverage_cap_during_probe_phase", "old": old, "new": new, "reason": "phase-2 escalation: controlled probe leverage cap increase"})
            old = float(s.get("max_probe_risk_fraction", bounds.get("max_probe_risk_fraction", {}).get("default", 0.35)) or 0.35)
            new = _bounded_step(old, bounds.get("max_probe_risk_fraction", {}), direction="up")
            if new != old:
                candidate_mutations.append({"param": "max_probe_risk_fraction", "old": old, "new": new, "reason": "phase-2 escalation: controlled probe risk increase"})
        else:
            high_wait_stall = float(target.get("non_actionable_wait_ratio", 0.0) or 0.0) >= 0.80
            old = bool(s.get("neutral_regime_participation_allow", bounds.get("neutral_regime_participation_allow", {}).get("default", False)))
            if not old:
                candidate_mutations.append({"param": "neutral_regime_participation_allow", "old": old, "new": True, "reason": "phase-1 probe: allow neutral regime participation"})

            old = float(s.get("min_regime_strength_for_probe_entries", bounds.get("min_regime_strength_for_probe_entries", {}).get("default", 0.50)) or 0.50)
            new = _bounded_step(old, bounds.get("min_regime_strength_for_probe_entries", {}), direction="down")
            if new != old:
                candidate_mutations.append({"param": "min_regime_strength_for_probe_entries", "old": old, "new": new, "reason": "phase-1 probe: lower minimum regime strength for probe entries"})

            old = float(s.get("actionable_confidence_min", bounds.get("actionable_confidence_min", {}).get("default", 0.58)) or 0.58)
            new = _bounded_step(old, bounds.get("actionable_confidence_min", {}), direction="down")
            if new != old:
                candidate_mutations.append({"param": "actionable_confidence_min", "old": old, "new": new, "reason": "phase-1 probe: lower actionable confidence threshold"})

            if not high_wait_stall:
                candidate_mutations.sort(key=lambda x: 0 if x.get("param") == "actionable_confidence_min" else 1)

            old = float(s.get("max_probe_risk_fraction", bounds.get("max_probe_risk_fraction", {}).get("default", 0.35)) or 0.35)
            if old > float(bounds.get("max_probe_risk_fraction", {}).get("default", 0.35)):
                new = _bounded_step(old, bounds.get("max_probe_risk_fraction", {}), direction="down")
                if new != old:
                    candidate_mutations.append({"param": "max_probe_risk_fraction", "old": old, "new": new, "reason": "phase-1 probe: keep risk bounded"})

            old = float(s.get("leverage_cap_during_probe_phase", bounds.get("leverage_cap_during_probe_phase", {}).get("default", 3.0)) or 3.0)
            if old > float(bounds.get("leverage_cap_during_probe_phase", {}).get("default", 3.0)):
                new = _bounded_step(old, bounds.get("leverage_cap_during_probe_phase", {}), direction="down")
                if new != old:
                    candidate_mutations.append({"param": "leverage_cap_during_probe_phase", "old": old, "new": new, "reason": "phase-1 probe: keep leverage cap bounded"})

            old = bool(s.get("leverage_escalation_gate_enabled", bounds.get("leverage_escalation_gate_enabled", {}).get("default", False)))
            if old:
                candidate_mutations.append({"param": "leverage_escalation_gate_enabled", "old": old, "new": False, "reason": "phase-1 probe: disable leverage escalation"})

        if rotate_family_hypothesis:
            candidate_mutations.sort(key=lambda x: 0 if x.get("param") in {"neutral_regime_participation_allow", "min_regime_strength_for_probe_entries"} else 1)

        for cm in candidate_mutations:
            sig = f"{cm.get('param')}:{cm.get('new')}"
            if sig in seen_deltas:
                continue
            return {
                "domain": "hyperliquid",
                "mode": mode,
                "param": cm["param"],
                "old": cm["old"],
                "new": cm["new"],
                "reason": cm["reason"],
                "context_note": "regime_actionability_limit_test",
                "mutation_mode": "limit_test",
                "limit_test_goal": goal,
                "limit_test_family": HL_REGIME_ACTIONABILITY_FAMILY,
                "limit_test_phase": phase,
                "anti_dead_end": {
                    "same_blocker_persistence": blocker_persist,
                    "rotate_after": rotate_after,
                    "rotated_hypothesis": rotate_family_hypothesis,
                    "blocked_reason": fam_memory.get("same_blocker_text", ""),
                },
                "phase_metrics": phase_metrics,
            }

        return None

    return None


def apply_mutation(surface: dict[str, Any], mutation: dict[str, Any]) -> None:
    mode = mutation["mode"]
    domain = mutation.get("domain")
    if domain == "kraken" and mode in ALLOWED_KRAKEN_MODES:
        surface.setdefault("kraken_overrides", {}).setdefault(mode, {})[mutation["param"]] = mutation["new"]
    elif domain == "hyperliquid" and mode in ALLOWED_HL_MODES:
        surface.setdefault("hyperliquid_overrides", {}).setdefault(mode, {})[mutation["param"]] = mutation["new"]


def run_cycle(api_base: str, apply: bool) -> dict[str, Any]:
    surface = load_json(SURFACE_FILE, {"version": 1, "kraken_overrides": {}, "hyperliquid_overrides": {}})
    kr, hl, news = fetch_state(api_base)

    analyses = []
    kr_modes = kr.get("modes") or {}
    if KRAKEN_LEARNER_MODE in kr_modes:
        analyses.append(classify_kraken_mode(KRAKEN_LEARNER_MODE, kr_modes.get(KRAKEN_LEARNER_MODE) or {}))
    analyses.append(classify_hl_mode(HYPERLIQUID_LEARNER_MODE, hl))

    mutation = propose_mutation(surface, analyses, news_context=news)
    if apply and mutation:
        apply_mutation(surface, mutation)
        save_json(SURFACE_FILE, surface)

    hl_overall = ((hl.get("metrics") or {}).get("strategy_overall") or {}).get(HYPERLIQUID_LEARNER_MODE, {})

    result = {
        "ts": now_iso(),
        "api_base": api_base,
        "apply": apply,
        "surface_file": str(SURFACE_FILE),
        "program_file": str(PROGRAM_FILE),
        "targets": {
            "kraken_baseline": KRAKEN_BASELINE_MODE,
            "kraken_learner": KRAKEN_LEARNER_MODE,
            "hyperliquid_baseline": HYPERLIQUID_BASELINE_MODE,
            "hyperliquid_learner": HYPERLIQUID_LEARNER_MODE,
        },
        "analyses": analyses,
        "mutation": mutation,
        "applied": bool(apply and mutation),
        "kraken_scan_time": ((kr.get("modes") or {}).get(KRAKEN_BASELINE_MODE) or {}).get("latest_scan_time"),
        "hl_active": hl.get("active_strategy_keys") or [hl.get("active_strategy_key")],
        "hl_learner_snapshot": {
            "mode": HYPERLIQUID_LEARNER_MODE,
            "sample_size": hl_overall.get("sample_closed"),
            "expectancy_net": hl_overall.get("expectancy_net"),
            "fee_drag_pct": hl_overall.get("fee_drag_pct"),
            "net_realized_pnl": hl_overall.get("net_realized_pnl"),
        },
        "news_context": {
            "news_risk": news.get("news_risk"),
            "news_bias": news.get("news_bias"),
            "source_confidence": news.get("source_confidence"),
            "summary": news.get("summary"),
            "why_it_matters": news.get("why_it_matters"),
        },
        "limit_test_policy": _limit_test_config(surface),
    }
    append_run(result)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Manual autoresearch-style experiment cycle runner (paper-only).")
    ap.add_argument("--api-base", default="http://127.0.0.1:8000")
    ap.add_argument("--apply", action="store_true", help="Apply one small mutation to editable surface")
    ap.add_argument("--cycles", type=int, default=1)
    ap.add_argument("--sleep-seconds", type=int, default=30)
    args = ap.parse_args()

    for i in range(max(1, args.cycles)):
        out = run_cycle(args.api_base, apply=args.apply)
        print(json.dumps(out, indent=2))
        if i < args.cycles - 1:
            time.sleep(max(1, args.sleep_seconds))


if __name__ == "__main__":
    main()
