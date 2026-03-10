from __future__ import annotations

import pandas as pd

from src.split import walk_forward_splits


def test_walkforward_produces_ordered_non_overlapping_folds():
    df = pd.DataFrame({"x": range(200)})
    folds = walk_forward_splits(df, n_folds=4, min_train_ratio=0.5)

    assert len(folds) == 4
    prev_end = 100
    for f in folds:
        assert len(f.train) >= 100
        assert len(f.test) > 0
        assert f.train.index.max() < f.test.index.min()
        assert f.test.index.min() >= prev_end
        prev_end = f.test.index.max()
