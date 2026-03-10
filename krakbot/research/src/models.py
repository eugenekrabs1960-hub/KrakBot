from __future__ import annotations

from sklearn.linear_model import LogisticRegression


def make_model(cfg: dict):
    model_type = cfg.get("type", "logistic_regression")
    if model_type != "logistic_regression":
        raise ValueError(f"Unsupported model type: {model_type}")

    return LogisticRegression(
        C=float(cfg.get("C", 1.0)),
        max_iter=int(cfg.get("max_iter", 1000)),
        class_weight=cfg.get("class_weight", "balanced"),
        random_state=int(cfg.get("random_state", 42)),
    )
