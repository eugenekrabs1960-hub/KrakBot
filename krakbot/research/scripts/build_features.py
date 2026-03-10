#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.features import build_features
from src.utils import ensure_parent, load_config, resolve_path


def _read_df(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.suffix == ".csv" else pd.read_parquet(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/baseline.yaml")
    args = parser.parse_args()

    research_dir = Path(__file__).resolve().parents[1]
    cfg = load_config(resolve_path(research_dir, args.config))

    in_path = resolve_path(research_dir, cfg["artifacts"]["dataset_path"])
    out_path = resolve_path(research_dir, cfg["artifacts"]["featured_path"])

    df = _read_df(in_path)
    feat = build_features(df, cfg["features"])

    ensure_parent(out_path)
    if out_path.suffix == ".csv":
        feat.to_csv(out_path, index=False)
    else:
        feat.to_parquet(out_path, index=False)

    print(f"Built features for {len(feat)} rows -> {out_path}")


if __name__ == "__main__":
    main()
