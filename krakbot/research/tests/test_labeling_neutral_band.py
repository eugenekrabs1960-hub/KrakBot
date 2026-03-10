from __future__ import annotations

import pandas as pd

from src.features import build_features


def _base_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open_ts": list(range(12)),
            "close_ts": list(range(1, 13)),
            "close": [100, 100.01, 100.0, 100.03, 100.01, 100.02, 100.02, 100.05, 100.0, 100.04, 100.02, 100.06],
            "volume": [10] * 12,
        }
    )


def test_neutral_band_drop_filters_rows():
    cfg = {
        "return_periods": [1],
        "volatility_window": 2,
        "momentum_window": 1,
        "rsi_window": 2,
        "volume_change_window": 1,
        "label_horizon": 1,
        "label_neutral_band_bps": 2,
        "neutral_handling": "drop",
        "dropna": True,
    }
    feat = build_features(_base_df(), cfg)
    assert "target_raw" in feat.columns
    assert (feat["target_raw"] == 0).sum() == 0


def test_neutral_band_keep_as_negative_keeps_rows():
    cfg = {
        "return_periods": [1],
        "volatility_window": 2,
        "momentum_window": 1,
        "rsi_window": 2,
        "volume_change_window": 1,
        "label_horizon": 1,
        "label_neutral_band_bps": 2,
        "neutral_handling": "keep_as_negative",
        "dropna": True,
    }
    feat = build_features(_base_df(), cfg)
    assert (feat["target_raw"] == 0).sum() >= 1
    assert set(feat["target"].unique()).issubset({0, 1})
