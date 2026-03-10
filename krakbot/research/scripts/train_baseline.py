#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.models import make_model
from src.split import time_series_split
from src.utils import ensure_parent, load_config, resolve_path, save_json

EXCLUDE_COLS = {"ts", "open_ts", "close_ts", "target", "future_return"}


def _read_df(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.suffix == ".csv" else pd.read_parquet(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/baseline.yaml")
    args = parser.parse_args()

    research_dir = Path(__file__).resolve().parents[1]
    cfg = load_config(resolve_path(research_dir, args.config))

    feat_path = resolve_path(research_dir, cfg["artifacts"]["featured_path"])
    model_path = resolve_path(research_dir, cfg["artifacts"]["model_path"])
    metadata_path = resolve_path(research_dir, cfg["artifacts"]["metadata_path"])

    df = _read_df(feat_path)
    split = time_series_split(df, **cfg["split"])

    feature_cols = [c for c in df.columns if c not in EXCLUDE_COLS]

    X_train = split.train[feature_cols]
    y_train = split.train["target"]
    X_val = split.val[feature_cols]
    y_val = split.val["target"]

    class_counts = y_train.value_counts().to_dict()
    if len(class_counts) < 2:
        raise RuntimeError(
            "Training split has only one class after labeling. "
            "Try increasing dataset range, reducing label_neutral_band_bps, or using label_horizon=1."
        )

    model = make_model(cfg["model"])
    model.fit(X_train, y_train)

    val_score = float(model.score(X_val, y_val))

    ensure_parent(model_path)
    joblib.dump({"model": model, "features": feature_cols}, model_path)

    meta = {
        "rows_total": int(len(df)),
        "rows_train": int(len(split.train)),
        "rows_val": int(len(split.val)),
        "rows_test": int(len(split.test)),
        "validation_accuracy": val_score,
        "feature_columns": feature_cols,
        "model_config": cfg["model"],
    }
    save_json(metadata_path, meta)
    print(f"Saved model to {model_path}")
    print(f"Saved metadata to {metadata_path}")


if __name__ == "__main__":
    main()
