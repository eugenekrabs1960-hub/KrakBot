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
    for r in hist:
        d = (r.get("decision") or r)
        st = d.get("status")
        if st == "WAIT":
            waits += 1
            rs = str(d.get("reason") or "")
            wait_reasons[rs] = wait_reasons.get(rs, 0) + 1
        elif st in {"PROPOSE_TRADE", "PAPER_TRADE_OPEN"}:
            actionable += 1

    dominant_reason = max(wait_reasons.items(), key=lambda x: x[1])[0] if wait_reasons else latest_reason
    wait_ratio = (waits / max(1, len(hist))) if hist else 0.0
    action_ratio = (actionable / max(1, len(hist))) if hist else 0.0

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
    }


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
        }

    if target["domain"] == "hyperliquid" and target["mode"] in ALLOWED_HL_MODES:
        mode = target["mode"]
        s = surface.setdefault("hyperliquid_overrides", {}).setdefault(mode, {})

        dom_reason = str(target.get("dominant_wait_reason") or "")
        wait_ratio = float(target.get("wait_ratio", 0.0) or 0.0)

        # Self-healing for cap-bound dead-end: open one extra slot (bounded).
        if "max positions reached" in dom_reason.lower() and wait_ratio >= 0.4:
            old_mp = int(s.get("max_positions", 2) or 2)
            new_mp = min(4, old_mp + 1)
            if new_mp != old_mp:
                return {
                    "domain": "hyperliquid",
                    "mode": mode,
                    "param": "max_positions",
                    "old": old_mp,
                    "new": new_mp,
                    "reason": "cap-bound self-healing mutation",
                    "context_note": "dead_end_unblock_max_positions",
                }

        # Self-healing for low-action no-entry dead-end: loosen momentum gate.
        current_gate = float(s.get("momentum_gate_min_atr_body", 0.18))
        gate_step = 0.01 if cautious else 0.03
        new_gate = round(max(0.08, current_gate - gate_step), 2)
        if new_gate != current_gate:
            return {
                "domain": "hyperliquid",
                "mode": mode,
                "param": "momentum_gate_min_atr_body",
                "old": current_gate,
                "new": new_gate,
                "reason": "small-step exploration under fixed evaluator",
                "context_note": "news_cautious_step" if cautious else "news_normal_step",
            }

        # If gate already low, try leverage-ceiling exploration (bounded).
        old_lev = float(s.get("max_leverage", 6.0) or 6.0)
        new_lev = min(10.0, round(old_lev + 1.0, 1))
        if new_lev != old_lev:
            return {
                "domain": "hyperliquid",
                "mode": mode,
                "param": "max_leverage",
                "old": old_lev,
                "new": new_lev,
                "reason": "bounded leverage exploration for learner",
                "context_note": "aggressive_hl_priority",
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
    surface = load_json(SURFACE_FILE, {"version": 1, "kraken_overrides": {}})
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
