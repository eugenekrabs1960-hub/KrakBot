from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .experiment_runner import run_cycle

BASE_DIR = Path(__file__).resolve().parent
AUTONOMY_STATE_FILE = BASE_DIR / "autonomy_state.json"
SURFACE_FILE = BASE_DIR / "experiment_surface.json"
RUNS_FILE = BASE_DIR / "experiment_runs.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ts_to_dt(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def load_state() -> dict[str, Any]:
    base = {
        "enabled": True,
        "last_tick": None,
        "last_apply": None,
        "pending_mutation": None,
        "daily_apply_count": 0,
        "daily_apply_date": None,
    }
    if not AUTONOMY_STATE_FILE.exists():
        return base
    try:
        raw = json.loads(AUTONOMY_STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            base.update(raw)
        # sanitize nullable counters from older files
        if base.get("daily_apply_count") is None:
            base["daily_apply_count"] = 0
        if base.get("enabled") is None:
            base["enabled"] = True
        return base
    except Exception:
        return base


def save_state(st: dict[str, Any]) -> None:
    AUTONOMY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTONOMY_STATE_FILE.write_text(json.dumps(st, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_surface() -> dict[str, Any]:
    try:
        return json.loads(SURFACE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "kraken_overrides": {}, "hyperliquid_overrides": {}}


def _save_surface(surface: dict[str, Any]) -> None:
    SURFACE_FILE.write_text(json.dumps(surface, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _set_override(domain: str, mode: str, param: str, value: Any) -> None:
    surface = _load_surface()
    key = "kraken_overrides" if domain == "kraken" else "hyperliquid_overrides"
    surface.setdefault(key, {}).setdefault(mode, {})[param] = value
    _save_surface(surface)


def _reset_daily_if_needed(st: dict[str, Any]) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    if st.get("daily_apply_date") != today:
        st["daily_apply_date"] = today
        st["daily_apply_count"] = 0


def _bottleneck_block(result: dict[str, Any]) -> str | None:
    analyses = result.get("analyses") or []
    mutation = result.get("mutation") or {}
    if not mutation:
        return None
    target_mode = mutation.get("mode")
    target = next((a for a in analyses if a.get("mode") == target_mode), None)
    if not target:
        return None

    # Hyperliquid-first policy: Kraken is near-frozen support unless very strong reason.
    if mutation.get("domain") == "kraken":
        if not (
            str(target.get("keep_discard")) == "discard_watch"
            and float(target.get("sample_size", 0) or 0) >= 30
            and float(target.get("fee_drag_pct", 0.0) or 0.0) < 200
        ):
            return "kraken_deprioritized_support_only"

    # Bottleneck-aware skips
    # Kraken: rr_min tweaks are not useful when fee-efficiency block dominates.
    if mutation.get("domain") == "kraken" and mutation.get("param") == "rr_min":
        if float(target.get("fee_drag_pct", 0.0) or 0.0) > 300:
            return "kraken_fee_drag_extreme_skip"

    # Hyperliquid: momentum gate tweaks are masked when max-position cap blocks entries.
    if mutation.get("domain") == "hyperliquid" and mutation.get("param") == "momentum_gate_min_atr_body":
        # Use learner snapshot+status as proxy; no apply when clearly cap-bound.
        hl_snap = result.get("hl_learner_snapshot") or {}
        if float(hl_snap.get("sample_size", 0) or 0) > 0 and float(hl_snap.get("fee_drag_pct", 0) or 0) > 500:
            # high drag with ongoing cap pressure usually means entries currently blocked/masked
            return "hyperliquid_cap_or_drag_mask_skip"

    return None


def _news_block(result: dict[str, Any]) -> str | None:
    n = result.get("news_context") or {}
    risk = str(n.get("news_risk", "low"))
    conf = str(n.get("source_confidence", "low"))
    # Advisory-aware: high-risk + medium/high confidence pauses auto-apply.
    if risk == "high" and conf in {"medium", "high"}:
        return "news_high_risk_pause"
    return None


def _append_autonomy_event(event: dict[str, Any]) -> None:
    RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RUNS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"autonomy_event": event}, ensure_ascii=False) + "\n")


def autonomy_tick(api_base: str = "http://127.0.0.1:8000") -> dict[str, Any]:
    st = load_state()
    _reset_daily_if_needed(st)

    dry = run_cycle(api_base=api_base, apply=False)
    mutation = dry.get("mutation")

    out: dict[str, Any] = {
        "ts": now_iso(),
        "enabled": bool(st.get("enabled", True)),
        "dry_run": dry,
        "action": "none",
        "reason": None,
    }

    if not st.get("enabled", True):
        st["last_tick"] = out["ts"]
        save_state(st)
        out["reason"] = "autonomy_disabled"
        return out

    # Auto-revert/keep review for pending mutation after grace window.
    pending = st.get("pending_mutation")
    if pending:
        p_ts = _ts_to_dt(pending.get("ts"))
        now = datetime.now(timezone.utc)
        if p_ts and (now - p_ts).total_seconds() >= 3 * 3600:
            mode = pending.get("mode")
            before = float(pending.get("before_expectancy", 0.0) or 0.0)
            current = None
            for a in (dry.get("analyses") or []):
                if a.get("mode") == mode:
                    current = float(a.get("expectancy_net", 0.0) or 0.0)
                    break
            if current is not None:
                if current < before - 0.05:
                    _set_override(pending.get("domain"), mode, pending.get("param"), pending.get("old"))
                    event = {
                        "ts": out["ts"],
                        "type": "auto_revert",
                        "mode": mode,
                        "param": pending.get("param"),
                        "from": pending.get("new"),
                        "to": pending.get("old"),
                        "before_expectancy": before,
                        "after_expectancy": current,
                    }
                    _append_autonomy_event(event)
                    out["action"] = "auto_revert"
                    out["reason"] = "expectancy_degraded"
                    st["pending_mutation"] = None
                else:
                    event = {
                        "ts": out["ts"],
                        "type": "auto_keep",
                        "mode": mode,
                        "param": pending.get("param"),
                        "value": pending.get("new"),
                        "before_expectancy": before,
                        "after_expectancy": current,
                    }
                    _append_autonomy_event(event)
                    out["action"] = "auto_keep"
                    out["reason"] = "mutation_stable_or_improved"
                    st["pending_mutation"] = None

    # Controlled auto-apply (bounded)
    if mutation and st.get("daily_apply_count", 0) < 2 and not st.get("pending_mutation"):
        b = _bottleneck_block(dry)
        if b:
            out["reason"] = b
        else:
            n = _news_block(dry)
            if n:
                out["reason"] = n
            else:
                applied = run_cycle(api_base=api_base, apply=True)
                out["action"] = "auto_apply"
                out["reason"] = "bounded_auto_apply"
                out["applied_run"] = applied
                st["last_apply"] = out["ts"]
                st["daily_apply_count"] = int(st.get("daily_apply_count", 0) or 0) + 1

                # Track pending mutation for later keep/revert review.
                mode = mutation.get("mode")
                current_expectancy = None
                for a in (dry.get("analyses") or []):
                    if a.get("mode") == mode:
                        current_expectancy = a.get("expectancy_net")
                        break
                st["pending_mutation"] = {
                    "ts": out["ts"],
                    "domain": mutation.get("domain"),
                    "mode": mode,
                    "param": mutation.get("param"),
                    "old": mutation.get("old"),
                    "new": mutation.get("new"),
                    "before_expectancy": current_expectancy,
                }

    st["last_tick"] = out["ts"]
    save_state(st)
    return out
