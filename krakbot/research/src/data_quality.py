from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.ingestion import timeframe_to_minutes
from src.utils import ensure_parent, save_json


def run_quality_checks(df: pd.DataFrame, timeframe: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    out = df.copy()
    out["ts"] = pd.to_datetime(out["ts"], utc=True)
    out = out.sort_values("ts").reset_index(drop=True)

    duplicate_count = int(out.duplicated(subset=["ts"]).sum())
    out = out.drop_duplicates(subset=["ts"], keep="last").reset_index(drop=True)

    monotonic = bool(out["ts"].is_monotonic_increasing)

    interval = pd.Timedelta(minutes=timeframe_to_minutes(timeframe))
    diffs = out["ts"].diff()
    missing_steps = diffs[diffs > interval]
    missing_intervals = []
    for idx, gap in missing_steps.items():
        missing_bars = int(gap / interval) - 1
        missing_intervals.append(
            {
                "after": out.loc[idx - 1, "ts"].isoformat(),
                "before": out.loc[idx, "ts"].isoformat(),
                "missing_bars": missing_bars,
            }
        )

    ohlc_bad = out[
        (out["high"] < out[["open", "close"]].max(axis=1))
        | (out["low"] > out[["open", "close"]].min(axis=1))
    ]

    report = {
        "rows": int(len(out)),
        "timeframe": timeframe,
        "monotonic_timestamps": monotonic,
        "duplicates_removed": duplicate_count,
        "missing_interval_count": int(len(missing_intervals)),
        "missing_intervals": missing_intervals[:50],
        "ohlc_sanity_violations": int(len(ohlc_bad)),
    }
    return out, report


def write_quality_report(research_dir: Path, report: dict[str, Any], prefix: str = "data_quality") -> None:
    reports_dir = research_dir / "reports"
    json_path = reports_dir / f"{prefix}.json"
    md_path = reports_dir / f"{prefix}.md"

    save_json(json_path, report)

    ensure_parent(md_path)
    lines = [
        "# Data Quality Report",
        "",
        f"- Rows: {report['rows']}",
        f"- Timeframe: {report['timeframe']}",
        f"- Monotonic timestamps: {report['monotonic_timestamps']}",
        f"- Duplicates removed: {report['duplicates_removed']}",
        f"- Missing interval gaps: {report['missing_interval_count']}",
        f"- OHLC sanity violations: {report['ohlc_sanity_violations']}",
        "",
    ]

    if report.get("missing_intervals"):
        lines.append("## Missing Interval Samples")
        for gap in report["missing_intervals"][:10]:
            lines.append(
                f"- {gap['after']} -> {gap['before']} (missing_bars={gap['missing_bars']})"
            )

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
