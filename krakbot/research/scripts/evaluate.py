#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt

sys.path.append(str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from src.benchmarks import benchmark_signals
from src.metrics import classification_metrics, trading_proxy_metrics
from src.models import make_model
from src.split import time_series_split, walk_forward_splits
from src.utils import ensure_parent, load_config, resolve_path, save_json

EXCLUDE_COLS = {"ts", "open_ts", "close_ts", "target", "future_return", "target_raw"}


def _read_df(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.suffix == ".csv" else pd.read_parquet(path)


def _eval_signal(y_true, future_return, signal) -> dict:
    y_pred = np.where(signal > 0, 1, 0)
    y_proba = np.where(signal > 0, 1.0, 0.0)
    return {
        "classification": classification_metrics(y_true, y_pred, y_proba),
        "trading_proxy": trading_proxy_metrics(signal, future_return),
    }


def _aggregate_fold_metrics(folds: list[dict]) -> dict:
    auc_vals = [f["classification"]["auc"] for f in folds if f["classification"]["auc"] is not None]
    bal_acc_vals = [f["classification"]["balanced_accuracy"] for f in folds]
    mcc_vals = [f["classification"]["mcc"] for f in folds]
    hit_vals = [f["trading_proxy"]["hit_rate"] for f in folds]

    return {
        "mean_balanced_accuracy": float(np.mean(bal_acc_vals)),
        "var_balanced_accuracy": float(np.var(bal_acc_vals)),
        "mean_mcc": float(np.mean(mcc_vals)),
        "var_mcc": float(np.var(mcc_vals)),
        "mean_auc": float(np.mean(auc_vals)) if auc_vals else None,
        "var_auc": float(np.var(auc_vals)) if auc_vals else None,
        "mean_hit_rate": float(np.mean(hit_vals)),
        "var_hit_rate": float(np.var(hit_vals)),
    }


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
    y_test = split.test["target"].to_numpy()
    future_return = split.test["future_return"].to_numpy()

    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= 0.5).astype(int)
    signal = np.where(y_pred == 1, 1.0, -1.0)

    cls = classification_metrics(y_test, y_pred, y_proba)
    trd = trading_proxy_metrics(signal, future_return)

    benchmarks = {}
    signals = benchmark_signals(split.test)
    for name, bsignal in signals.items():
        benchmarks[name] = _eval_signal(y_test, future_return, bsignal)

    benchmark_deltas = {
        name: {
            "delta_balanced_accuracy": cls["balanced_accuracy"] - bench["classification"]["balanced_accuracy"],
            "delta_mcc": cls["mcc"] - bench["classification"]["mcc"],
            "delta_hit_rate": trd["hit_rate"] - bench["trading_proxy"]["hit_rate"],
            "delta_cumulative_return": trd["cumulative_return"] - bench["trading_proxy"]["cumulative_return"],
        }
        for name, bench in benchmarks.items()
    }

    wf_cfg = cfg.get("walk_forward", {"enabled": True, "n_folds": 5, "min_train_ratio": 0.5})
    walk_forward = {"enabled": bool(wf_cfg.get("enabled", True)), "folds": []}
    if walk_forward["enabled"]:
        folds = walk_forward_splits(
            df,
            n_folds=int(wf_cfg.get("n_folds", 5)),
            min_train_ratio=float(wf_cfg.get("min_train_ratio", 0.5)),
        )
        for fold in folds:
            X_train = fold.train[feature_cols]
            y_train = fold.train["target"]
            if y_train.nunique() < 2:
                raise RuntimeError(
                    f"Walk-forward fold {fold.fold_idx} training split has one class only. "
                    "Increase rows, reduce neutral band, or lower fold count."
                )

            m = make_model(cfg["model"])
            m.fit(X_train, y_train)

            X_fold = fold.test[feature_cols]
            y_fold = fold.test["target"].to_numpy()
            ret_fold = fold.test["future_return"].to_numpy()
            p_fold = m.predict_proba(X_fold)[:, 1]
            pred_fold = (p_fold >= 0.5).astype(int)
            sig_fold = np.where(pred_fold == 1, 1.0, -1.0)

            walk_forward["folds"].append(
                {
                    "fold": fold.fold_idx,
                    "rows_train": int(len(fold.train)),
                    "rows_test": int(len(fold.test)),
                    "classification": classification_metrics(y_fold, pred_fold, p_fold),
                    "trading_proxy": trading_proxy_metrics(sig_fold, ret_fold),
                }
            )

        walk_forward["aggregate"] = _aggregate_fold_metrics(walk_forward["folds"])

    metrics = {
        "classification": cls,
        "trading_proxy": trd,
        "benchmarks": benchmarks,
        "benchmark_deltas": benchmark_deltas,
        "walk_forward": walk_forward,
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

## Model Classification Metrics
- Accuracy: {cls['accuracy']:.4f}
- Balanced Accuracy: {cls['balanced_accuracy']:.4f}
- Precision: {cls['precision']:.4f}
- Recall: {cls['recall']:.4f}
- MCC: {cls['mcc']:.4f}
- AUC: {cls['auc'] if cls['auc'] is not None else 'N/A'}
- Confusion Matrix: TN={cls['confusion_matrix']['tn']} FP={cls['confusion_matrix']['fp']} FN={cls['confusion_matrix']['fn']} TP={cls['confusion_matrix']['tp']}

## Trading Proxy Metrics (Frictionless)
- Hit Rate: {trd['hit_rate']:.4f}
- Avg Return / Signal: {trd['avg_return_per_signal']:.6f}
- Cumulative Return: {trd['cumulative_return']:.4f}
- Max Drawdown: {trd['max_drawdown']:.4f}
- Turnover Proxy: {trd['turnover_proxy']:.4f}
- Signal Count: {trd['signal_count']}

## Benchmarks
"""

    for name, bench in benchmarks.items():
        summary += (
            f"- {name}: bal_acc={bench['classification']['balanced_accuracy']:.4f}, "
            f"mcc={bench['classification']['mcc']:.4f}, hit_rate={bench['trading_proxy']['hit_rate']:.4f}, "
            f"cum_ret={bench['trading_proxy']['cumulative_return']:.4f}\n"
        )

    summary += "\n## Benchmark Deltas (Model - Benchmark)\n"
    for name, d in benchmark_deltas.items():
        summary += (
            f"- {name}: Δbal_acc={d['delta_balanced_accuracy']:.4f}, "
            f"Δmcc={d['delta_mcc']:.4f}, Δhit_rate={d['delta_hit_rate']:.4f}, "
            f"Δcum_ret={d['delta_cumulative_return']:.4f}\n"
        )

    if walk_forward.get("enabled") and walk_forward.get("folds"):
        agg = walk_forward["aggregate"]
        summary += f"""

## Walk-Forward Validation
- Folds: {len(walk_forward['folds'])}
- Mean Balanced Accuracy: {agg['mean_balanced_accuracy']:.4f} (var {agg['var_balanced_accuracy']:.6f})
- Mean MCC: {agg['mean_mcc']:.4f} (var {agg['var_mcc']:.6f})
- Mean Hit Rate: {agg['mean_hit_rate']:.4f} (var {agg['var_hit_rate']:.6f})
"""

    summary += """
Artifacts:
- metrics.json
- plots/equity_curve.png
"""

    with open(reports_dir / "summary.md", "w", encoding="utf-8") as f:
        f.write(summary)

    print(f"Saved reports in {reports_dir}")


if __name__ == "__main__":
    main()
