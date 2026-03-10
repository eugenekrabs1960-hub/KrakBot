#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def evaluate_gate(metrics: dict[str, Any], gate_cfg: dict[str, Any]) -> dict[str, Any]:
    cls = metrics.get("classification", {})
    trd = metrics.get("trading_proxy", {})
    deltas = metrics.get("benchmark_deltas", {})

    min_bal_acc = float(gate_cfg.get("min_balanced_accuracy", 0.0))
    min_mcc = float(gate_cfg.get("min_mcc", -1.0))
    min_signal_count = int(gate_cfg.get("min_signal_count", 0))
    max_drawdown_floor = gate_cfg.get("max_drawdown_floor", None)

    checks: list[dict[str, Any]] = []

    bal_acc = float(cls.get("balanced_accuracy", 0.0))
    checks.append(
        _check(
            "min_balanced_accuracy",
            bal_acc >= min_bal_acc,
            f"observed={bal_acc:.6f}, required>={min_bal_acc:.6f}",
        )
    )

    mcc = float(cls.get("mcc", 0.0))
    checks.append(
        _check("min_mcc", mcc >= min_mcc, f"observed={mcc:.6f}, required>={min_mcc:.6f}")
    )

    signal_count = int(trd.get("signal_count", 0))
    checks.append(
        _check(
            "min_signal_count",
            signal_count >= min_signal_count,
            f"observed={signal_count}, required>={min_signal_count}",
        )
    )

    if max_drawdown_floor is not None:
        observed_mdd = float(trd.get("max_drawdown", 0.0))
        floor = float(max_drawdown_floor)
        checks.append(
            _check(
                "max_drawdown_floor",
                observed_mdd >= floor,
                f"observed={observed_mdd:.6f}, required>={floor:.6f}",
            )
        )

    if bool(gate_cfg.get("require_outperform_always_long", False)):
        d = float(deltas.get("always_long", {}).get("delta_cumulative_return", 0.0))
        checks.append(
            _check(
                "require_outperform_always_long",
                d > 0.0,
                f"delta_cumulative_return={d:.6f}, required>0",
            )
        )

    if bool(gate_cfg.get("require_outperform_always_short", False)):
        d = float(deltas.get("always_short", {}).get("delta_cumulative_return", 0.0))
        checks.append(
            _check(
                "require_outperform_always_short",
                d > 0.0,
                f"delta_cumulative_return={d:.6f}, required>0",
            )
        )

    wf = metrics.get("walk_forward", {})
    wf_folds = wf.get("folds", []) if isinstance(wf, dict) else []
    min_folds_passing = gate_cfg.get("min_folds_passing", None)
    if wf.get("enabled") and wf_folds and min_folds_passing is not None:
        required = int(min_folds_passing)
        passing = 0
        fold_details = []

        for fold in wf_folds:
            f_cls = fold.get("classification", {})
            f_trd = fold.get("trading_proxy", {})

            f_bal = float(f_cls.get("balanced_accuracy", 0.0))
            f_mcc = float(f_cls.get("mcc", 0.0))
            f_sig = int(f_trd.get("signal_count", 0))
            f_mdd = float(f_trd.get("max_drawdown", 0.0))

            pass_fold = (f_bal >= min_bal_acc) and (f_mcc >= min_mcc) and (f_sig >= min_signal_count)
            if max_drawdown_floor is not None:
                pass_fold = pass_fold and (f_mdd >= float(max_drawdown_floor))

            if pass_fold:
                passing += 1

            fold_details.append(
                f"fold={fold.get('fold')}: pass={pass_fold} bal_acc={f_bal:.4f} mcc={f_mcc:.4f} signals={f_sig} mdd={f_mdd:.4f}"
            )

        checks.append(
            _check(
                "min_folds_passing",
                passing >= required,
                f"observed={passing}/{len(wf_folds)} required>={required}; " + "; ".join(fold_details[:5]),
            )
        )

    passed = [c for c in checks if c["passed"]]
    failed = [c for c in checks if not c["passed"]]
    verdict = "GO" if not failed else "NO_GO"

    return {
        "verdict": verdict,
        "checks": checks,
        "passed": passed,
        "failed": failed,
    }


def write_markdown(report_path: Path, gate_result: dict[str, Any], metrics_path: Path, gate_cfg_path: Path) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Baseline Gate Verdict",
        "",
        f"- Verdict: **{gate_result['verdict']}**",
        f"- Generated: {ts}",
        f"- Metrics: `{metrics_path}`",
        f"- Gate Config: `{gate_cfg_path}`",
        "",
        "## Passed Criteria",
    ]

    if gate_result["passed"]:
        for item in gate_result["passed"]:
            lines.append(f"- ✅ `{item['name']}` — {item['detail']}")
    else:
        lines.append("- None")

    lines.append("")
    lines.append("## Failed Criteria")
    if gate_result["failed"]:
        for item in gate_result["failed"]:
            lines.append(f"- ❌ `{item['name']}` — {item['detail']}")
    else:
        lines.append("- None")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate GO/NO_GO gate from reports/metrics.json")
    parser.add_argument("--metrics", default="reports/metrics.json")
    parser.add_argument("--gate-config", default="configs/eval_gate.yaml")
    parser.add_argument("--report", default="reports/gate_verdict.md")
    parser.add_argument("--json-out", default="reports/gate_verdict.json")
    args = parser.parse_args()

    research_dir = Path(__file__).resolve().parents[1]
    metrics_path = (research_dir / args.metrics).resolve() if not Path(args.metrics).is_absolute() else Path(args.metrics)
    gate_cfg_path = (research_dir / args.gate_config).resolve() if not Path(args.gate_config).is_absolute() else Path(args.gate_config)
    report_path = (research_dir / args.report).resolve() if not Path(args.report).is_absolute() else Path(args.report)
    json_path = (research_dir / args.json_out).resolve() if not Path(args.json_out).is_absolute() else Path(args.json_out)

    metrics = _load_json(metrics_path)
    gate_cfg = _load_yaml(gate_cfg_path)
    result = evaluate_gate(metrics, gate_cfg)

    write_markdown(report_path, result, metrics_path, gate_cfg_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    print(f"VERDICT: {result['verdict']}")
    if result["failed"]:
        print("FAILED:")
        for item in result["failed"]:
            print(f"- {item['name']}: {item['detail']}")
    else:
        print("All gate checks passed.")


if __name__ == "__main__":
    main()
