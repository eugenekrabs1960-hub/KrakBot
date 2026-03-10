#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from src.dataset import ExportConfig, export_candles_with_optional_trades
from src.utils import ensure_parent, load_config, resolve_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/baseline.yaml")
    parser.add_argument("--database-url", required=True, help="SQLAlchemy Postgres URL")
    args = parser.parse_args()

    research_dir = Path(__file__).resolve().parents[1]
    cfg = load_config(resolve_path(research_dir, args.config))
    dcfg = cfg["dataset"]
    artifact_cfg = cfg["artifacts"]

    out_path = resolve_path(research_dir, artifact_cfg["dataset_path"])

    export_cfg = ExportConfig(
        database_url=args.database_url,
        market=dcfg.get("market", "SOL/USD"),
        timeframe=dcfg.get("timeframe", "1m"),
        start_ts=dcfg.get("start_ts"),
        end_ts=dcfg.get("end_ts"),
        use_market_trades=bool(dcfg.get("use_market_trades", True)),
    )

    df = export_candles_with_optional_trades(export_cfg)
    if len(df) < int(dcfg.get("min_rows", 500)):
        raise RuntimeError(f"Not enough rows exported: {len(df)}")

    ensure_parent(out_path)
    if out_path.suffix == ".csv":
        df.to_csv(out_path, index=False)
    else:
        df.to_parquet(out_path, index=False)

    print(f"Exported {len(df)} rows to {out_path}")


if __name__ == "__main__":
    main()
