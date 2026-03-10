from __future__ import annotations

import numpy as np
import pandas as pd


def compute_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_gain = up.rolling(window=window, min_periods=window).mean()
    avg_loss = down.rolling(window=window, min_periods=window).mean()
    rs = avg_gain / (avg_loss.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def build_features(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    out = df.copy()

    out["ret_1"] = out["close"].pct_change(1)
    for p in cfg["return_periods"]:
        out[f"ret_{p}"] = out["close"].pct_change(p)

    out["rolling_volatility"] = out["ret_1"].rolling(
        window=cfg["volatility_window"], min_periods=cfg["volatility_window"]
    ).std()
    out["momentum"] = out["close"] / out["close"].shift(cfg["momentum_window"]) - 1.0
    out["rsi_like"] = compute_rsi(out["close"], window=cfg["rsi_window"])
    out["volume_change"] = out["volume"].pct_change(cfg.get("volume_change_window", 1))

    horizon = int(cfg["label_horizon"])
    out["future_return"] = out["close"].shift(-horizon) / out["close"] - 1.0
    out["target"] = (out["future_return"] > 0).astype(int)

    if cfg.get("dropna", True):
        out = out.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)

    return out
