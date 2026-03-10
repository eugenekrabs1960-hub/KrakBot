#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.metrics import classification_metrics, trading_proxy_metrics
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
    reports_dir = resolve_path(research_dir, cfg["artifacts"]["reports_dir"])

    feat_path = resolve_path(research_dir, cfg["artifacts"]["featured_path"])
    model_path = resolve_path(research_dir, cfg["artifacts"]["model_path"])
    pred_path = resolve_path(research_dir, cfg["artifacts"]["predictions_path"])

    df = _read_df(feat_path)
    split = time_series_split(df, **cfg["split"])

    payload = joblib.load(model_path)
    model = payload["model"]
    feature_cols = payload.get("features") or [c for c in df.columns if c not in EXCLUDE_COLS]

    X_test = split.test[feature_cols]
    y_test = split.test["target"]
    future_return = split.test["future_return"].to_numpy()

    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= 0.5).astype(int)
    signal = np.where(y_pred == 1, 1.0, -1.0)

    cls = classification_metrics(y_test, y_pred, y_proba)
    trd = trading_proxy_metrics(signal, future_return)

    metrics = {
        "classification": cls,
        "trading_proxy": trd,
        "rows_test": int(len(split.test)),
    }

    ensure_parent(reports_dir / "metrics.json")
    save_json(reports_dir / "metrics.json", metrics)

    test_preds = split.test.copy()
    test_preds["y_pred"] = y_pred
    test_preds["y_proba"] = y_proba
    test_preds["signal"] = signal
    test_preds["strategy_return"] = signal * future_return
    if pred_path.suffix == ".csv":
        test_preds.to_csv(pred_path, index=False)
    else:
        test_preds.to_parquet(pred_path, index=False)

    equity = np.cumprod(1.0 + test_preds["strategy_return"].to_numpy())
    plot_path = reports_dir / "plots" / "equity_curve.png"
    ensure_parent(plot_path)
    plt.figure(figsize=(10, 4))
    plt.plot(equity)
    plt.title("Baseline Proxy Equity Curve (Frictionless)")
    plt.xlabel("Test Bars")
    plt.ylabel("Equity")
    plt.tight_layout()
    plt.savefig(plot_path, dpi=140)
    plt.close()

    summary = f"""# Baseline Research Summary

## Classification Metrics
- Accuracy: {cls['accuracy']:.4f}
- Precision: {cls['precision']:.4f}
- Recall: {cls['recall']:.4f}
- AUC: {cls['auc'] if cls['auc'] is not None else 'N/A'}

## Trading Proxy Metrics (Frictionless)
- Hit Rate: {trd['hit_rate']:.4f}
- Avg Return / Signal: {trd['avg_return_per_signal']:.6f}
- Cumulative Return: {trd['cumulative_return']:.4f}
- Max Drawdown: {trd['max_drawdown']:.4f}

Artifacts:
- metrics.json
- plots/equity_curve.png
"""

    with open(reports_dir / "summary.md", "w", encoding="utf-8") as f:
        f.write(summary)

    print(f"Saved reports in {reports_dir}")


if __name__ == "__main__":
    main()
