from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml


RESEARCH_DIR = Path(__file__).resolve().parents[1]


def test_export_low_rows_actionable_message(tmp_path):
    csv_path = tmp_path / "tiny.csv"
    pd.DataFrame(
        {
            "timestamp": [1, 2, 3],
            "open": [1, 1, 1],
            "high": [1, 1, 1],
            "low": [1, 1, 1],
            "close": [1, 1, 1],
            "volume": [1, 1, 1],
        }
    ).to_csv(csv_path, index=False)

    cfg = {
        "dataset": {
            "source": "external_csv",
            "timeframe": "1m",
            "min_rows": 50,
            "external_csv": {
                "path": str(csv_path),
                "timezone": "UTC",
                "column_mapping": {
                    "timestamp": "timestamp",
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "volume": "volume",
                },
            },
        },
        "artifacts": {"dataset_path": str(tmp_path / "dataset.parquet")},
    }
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "scripts/export_dataset.py", "--config", str(cfg_path)],
        cwd=RESEARCH_DIR,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "need at least" in (proc.stderr + proc.stdout)


def test_train_one_class_actionable_message(tmp_path):
    feat_path = tmp_path / "feat.parquet"
    model_path = tmp_path / "model.joblib"
    metadata_path = tmp_path / "meta.json"

    df = pd.DataFrame(
        {
            "open_ts": range(100),
            "close_ts": range(1, 101),
            "close": [1.0] * 100,
            "volume": [1.0] * 100,
            "ret_1": [0.0] * 100,
            "rolling_volatility": [0.0] * 100,
            "momentum": [0.0] * 100,
            "rsi_like": [50.0] * 100,
            "volume_change": [0.0] * 100,
            "future_return": [0.0] * 100,
            "target": [1] * 100,
        }
    )
    df.to_parquet(feat_path, index=False)

    cfg = {
        "split": {"train_ratio": 0.7, "val_ratio": 0.15, "test_ratio": 0.15},
        "model": {"type": "logistic_regression", "class_weight": "balanced", "C": 1.0, "max_iter": 100},
        "artifacts": {
            "featured_path": str(feat_path),
            "model_path": str(model_path),
            "metadata_path": str(metadata_path),
        },
    }
    cfg_path = tmp_path / "train_cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "scripts/train_baseline.py", "--config", str(cfg_path)],
        cwd=RESEARCH_DIR,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "only one class" in (proc.stderr + proc.stdout)
