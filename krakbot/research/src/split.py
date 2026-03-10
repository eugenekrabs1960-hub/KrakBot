from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class TimeSplit:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame


@dataclass
class WalkForwardFold:
    fold_idx: int
    train: pd.DataFrame
    test: pd.DataFrame


def time_series_split(df: pd.DataFrame, train_ratio: float, val_ratio: float, test_ratio: float) -> TimeSplit:
    total = len(df)
    if total < 10:
        raise ValueError("Not enough rows for split")

    if round(train_ratio + val_ratio + test_ratio, 6) != 1.0:
        raise ValueError("train/val/test ratios must sum to 1.0")

    train_end = int(total * train_ratio)
    val_end = train_end + int(total * val_ratio)

    train = df.iloc[:train_end].copy()
    val = df.iloc[train_end:val_end].copy()
    test = df.iloc[val_end:].copy()

    if train.empty or val.empty or test.empty:
        raise ValueError("One of split partitions is empty; adjust ratios or data window")

    return TimeSplit(train=train, val=val, test=test)


def walk_forward_splits(df: pd.DataFrame, n_folds: int = 5, min_train_ratio: float = 0.5) -> list[WalkForwardFold]:
    total = len(df)
    if n_folds < 2:
        raise ValueError("walk-forward requires n_folds >= 2")

    min_train_rows = int(total * min_train_ratio)
    if min_train_rows < 20:
        raise ValueError("walk-forward min train window too small; increase data rows")

    remaining = total - min_train_rows
    fold_size = remaining // n_folds
    if fold_size < 5:
        raise ValueError(
            f"walk-forward fold size too small ({fold_size}); increase rows or reduce n_folds"
        )

    folds: list[WalkForwardFold] = []
    for i in range(n_folds):
        test_start = min_train_rows + i * fold_size
        test_end = min(total, test_start + fold_size if i < n_folds - 1 else total)
        if test_end <= test_start:
            continue

        train = df.iloc[:test_start].copy()
        test = df.iloc[test_start:test_end].copy()
        if train.empty or test.empty:
            continue
        folds.append(WalkForwardFold(fold_idx=i + 1, train=train, test=test))

    if not folds:
        raise ValueError("walk-forward split produced no folds")

    return folds
