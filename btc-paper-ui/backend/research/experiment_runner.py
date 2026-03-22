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

ALLOWED_MODES = {
    "btc_15m_conservative_netedge_v1",
    "btc_15m_conservative_inverse_v1",
    "btc_15m_breakout_retest",
}


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


def classify_mode(mode_key: str, mode_state: dict[str, Any]) -> dict[str, Any]:
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
        "mode": mode_key,
        "comparator_verdict": cmp_verdict,
        "mode_review": review,
        "sample_size": sample,
        "expectancy_net": expectancy,
        "fee_drag_pct": fee_drag,
        "keep_discard": keep_discard,
    }


def propose_mutation(surface: dict[str, Any], analyses: list[dict[str, Any]]) -> dict[str, Any] | None:
    # Target one inconclusive/weak mode with smallest sample first.
    candidates = [a for a in analyses if a["mode"] in ALLOWED_MODES and a["keep_discard"] in {"inconclusive", "probation", "discard_watch"}]
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x["sample_size"], x["expectancy_net"]))
    target = candidates[0]["mode"]

    s = surface.setdefault("kraken_overrides", {}).setdefault(target, {})
    default_rr = {
        "btc_15m_conservative_inverse_v1": 0.5,
        "btc_15m_breakout_retest": 1.35,
    }.get(target, 1.5)
    current_rr = float(s.get("rr_min", default_rr))

    floor = 0.35 if target == "btc_15m_conservative_inverse_v1" else (1.10 if target == "btc_15m_breakout_retest" else 1.20)
    new_rr = round(max(floor, current_rr - 0.05), 2)
    if new_rr == current_rr:
        return None

    return {
        "mode": target,
        "param": "rr_min",
        "old": current_rr,
        "new": new_rr,
        "reason": "small-step exploration under fixed evaluator",
    }


def apply_mutation(surface: dict[str, Any], mutation: dict[str, Any]) -> None:
    mode = mutation["mode"]
    if mode not in ALLOWED_MODES:
        return
    surface.setdefault("kraken_overrides", {}).setdefault(mode, {})[mutation["param"]] = mutation["new"]


def run_cycle(api_base: str, apply: bool) -> dict[str, Any]:
    surface = load_json(SURFACE_FILE, {"version": 1, "kraken_overrides": {}})
    kr, hl, news = fetch_state(api_base)

    analyses = []
    for mode, st in (kr.get("modes") or {}).items():
        if mode == "btc_15m_conservative":
            continue
        analyses.append(classify_mode(mode, st or {}))

    mutation = propose_mutation(surface, analyses)
    if apply and mutation:
        apply_mutation(surface, mutation)
        save_json(SURFACE_FILE, surface)

    result = {
        "ts": now_iso(),
        "api_base": api_base,
        "apply": apply,
        "surface_file": str(SURFACE_FILE),
        "program_file": str(PROGRAM_FILE),
        "analyses": analyses,
        "mutation": mutation,
        "applied": bool(apply and mutation),
        "kraken_scan_time": ((kr.get("modes") or {}).get("btc_15m_conservative") or {}).get("latest_scan_time"),
        "hl_active": hl.get("active_strategy_keys") or [hl.get("active_strategy_key")],
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
