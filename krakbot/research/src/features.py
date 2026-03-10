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

    horizon = int(cfg.get("label_horizon", 1))
    neutral_band_bps = float(cfg.get("label_neutral_band_bps", 0.0))
    band = neutral_band_bps / 10000.0

    out["future_return"] = out["close"].shift(-horizon) / out["close"] - 1.0

    out["target_raw"] = np.select(
        [out["future_return"] > band, out["future_return"] < -band],
        [1, -1],
        default=0,
    )

    # Deterministic binary path for model training.
    # - If band=0, equivalent to original target=(future_return > 0).
    # - If band>0 and neutral_handling=drop, neutral rows are excluded.
    # - If band>0 and neutral_handling=keep_as_negative, neutral labels map to class 0.
    neutral_handling = cfg.get("neutral_handling", "drop")
    if neutral_band_bps > 0 and neutral_handling == "drop":
        out = out[out["target_raw"] != 0].copy()

    out["target"] = (out["target_raw"] == 1).astype(int)

    if cfg.get("dropna", True):
        out = out.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)

    return out
