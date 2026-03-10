from __future__ import annotations

import numpy as np
import pandas as pd


def benchmark_signals(df: pd.DataFrame) -> dict[str, np.ndarray]:
    n = len(df)
    momentum_raw = np.where(df["ret_1"].fillna(0.0).to_numpy() >= 0, 1.0, -1.0)
    return {
        "always_long": np.ones(n),
        "always_short": -np.ones(n),
        "momentum": momentum_raw,
    }
