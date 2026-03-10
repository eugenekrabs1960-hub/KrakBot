from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    matthews_corrcoef,
    precision_recall_fscore_support,
    precision_score,
    recall_score,
    roc_auc_score,
)


def classification_metrics(y_true, y_pred, y_proba) -> dict:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    p, r, _, _ = precision_recall_fscore_support(y_true, y_pred, labels=[0, 1], zero_division=0)

    out = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "mcc": float(matthews_corrcoef(y_true, y_pred)),
        "precision_by_class": {"0": float(p[0]), "1": float(p[1])},
        "recall_by_class": {"0": float(r[0]), "1": float(r[1])},
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }
    try:
        out["auc"] = float(roc_auc_score(y_true, y_proba))
    except Exception:
        out["auc"] = None
    return out


def trading_proxy_metrics(signal, realized_return) -> dict:
    signal = np.asarray(signal)
    realized_return = np.asarray(realized_return)

    strategy_ret = signal * realized_return
    equity = np.cumprod(1.0 + strategy_ret)
    running_max = np.maximum.accumulate(equity)
    drawdown = (equity / running_max) - 1.0

    signal_changes = np.abs(np.diff(signal))

    return {
        "hit_rate": float(np.mean(strategy_ret > 0)),
        "avg_return_per_signal": float(np.mean(strategy_ret)),
        "cumulative_return": float(equity[-1] - 1.0) if len(equity) else 0.0,
        "max_drawdown": float(np.min(drawdown)) if len(drawdown) else 0.0,
        "signal_count": int(len(signal)),
        "turnover_proxy": float(np.mean(signal_changes > 0)) if len(signal_changes) else 0.0,
    }
