#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.data_quality import run_quality_checks, write_quality_report
from src.ingestion import load_dataset_by_source
from src.utils import ensure_parent, load_config, resolve_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/baseline.yaml")
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy Postgres URL (required when dataset.source=local_db)",
    )
    args = parser.parse_args()

    research_dir = Path(__file__).resolve().parents[1]
    cfg = load_config(resolve_path(research_dir, args.config))
    dcfg = cfg["dataset"]
    artifact_cfg = cfg["artifacts"]

    out_path = resolve_path(research_dir, artifact_cfg["dataset_path"])

    db_url = args.database_url or os.getenv("DATABASE_URL") or os.getenv("KRAKBOT_DATABASE_URL")

    df = load_dataset_by_source(research_dir, dcfg, database_url=db_url)
    df, quality_report = run_quality_checks(df, timeframe=dcfg.get("timeframe", "1m"))
    write_quality_report(research_dir, quality_report)

    if len(df) < int(dcfg.get("min_rows", 500)):
        raise RuntimeError(f"Not enough rows exported: {len(df)}")

    ensure_parent(out_path)
    if out_path.suffix == ".csv":
        df.to_csv(out_path, index=False)
    else:
        df.to_parquet(out_path, index=False)

    print(f"Exported {len(df)} rows to {out_path}")
    print(f"Data quality report -> {research_dir / 'reports' / 'data_quality.json'}")


if __name__ == "__main__":
    main()
