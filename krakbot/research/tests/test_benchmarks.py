from __future__ import annotations

import numpy as np
import pandas as pd

from src.benchmarks import benchmark_signals


def test_benchmark_signal_shapes_and_values():
    df = pd.DataFrame({"ret_1": [0.01, -0.02, 0.0, 0.03]})
    sig = benchmark_signals(df)

    assert set(sig.keys()) == {"always_long", "always_short", "momentum"}
    assert np.all(sig["always_long"] == 1.0)
    assert np.all(sig["always_short"] == -1.0)
    assert sig["momentum"].tolist() == [1.0, -1.0, 1.0, 1.0]
