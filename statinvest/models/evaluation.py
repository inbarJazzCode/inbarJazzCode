"""Leakage-resistant, time-aware evaluation utilities.

For time-indexed data we use *chronological* train/validation/test splits and
walk-forward evaluation. Preprocessing (e.g. standardization) must be fitted on
the training portion only — the helpers here return index arrays so callers can
enforce that discipline.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ChronoSplit:
    train_idx: np.ndarray
    val_idx: np.ndarray
    test_idx: np.ndarray

    def describe(self) -> dict:
        return {
            "n_train": int(len(self.train_idx)),
            "n_val": int(len(self.val_idx)),
            "n_test": int(len(self.test_idx)),
            "train_range": _range(self.train_idx),
            "val_range": _range(self.val_idx),
            "test_range": _range(self.test_idx),
        }


def _range(idx: np.ndarray):
    if len(idx) == 0:
        return None
    return [int(idx[0]), int(idx[-1])]


def chronological_split(
    n: int, train_frac: float = 0.6, val_frac: float = 0.2
) -> ChronoSplit:
    """Split ``n`` time-ordered observations without shuffling.

    The data is assumed already sorted ascending in time. No index appears in
    more than one partition, and every training index precedes every validation
    index, which precedes every test index — preventing look-ahead leakage.
    """
    if n <= 0:
        raise ValueError("n must be positive.")
    if not (0 < train_frac < 1) or not (0 <= val_frac < 1) or train_frac + val_frac >= 1:
        raise ValueError("Require 0<train_frac, 0<=val_frac and train_frac+val_frac<1.")
    n_train = int(np.floor(n * train_frac))
    n_val = int(np.floor(n * val_frac))
    n_train = max(n_train, 1)
    train_idx = np.arange(0, n_train)
    val_idx = np.arange(n_train, n_train + n_val)
    test_idx = np.arange(n_train + n_val, n)
    return ChronoSplit(train_idx, val_idx, test_idx)


def walk_forward_splits(
    n: int, n_folds: int = 5, min_train: int | None = None
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Expanding-window walk-forward splits.

    Yields ``(train_idx, test_idx)`` pairs where each training window strictly
    precedes its test window and windows grow over time.
    """
    if n_folds < 1:
        raise ValueError("n_folds must be >= 1.")
    if min_train is None:
        min_train = max(n // (n_folds + 1), 1)
    if min_train >= n:
        raise ValueError("min_train too large for the number of observations.")
    fold_size = max((n - min_train) // n_folds, 1)
    splits = []
    start_test = min_train
    for _ in range(n_folds):
        end_test = min(start_test + fold_size, n)
        if start_test >= n:
            break
        train_idx = np.arange(0, start_test)
        test_idx = np.arange(start_test, end_test)
        splits.append((train_idx, test_idx))
        start_test = end_test
        if start_test >= n:
            break
    return splits


def naive_baseline_prediction(y_train: np.ndarray, n_test: int) -> np.ndarray:
    """Persistence/mean baseline: predict the last training value."""
    y_train = np.asarray(y_train, dtype=float).ravel()
    last = y_train[-1] if len(y_train) else 0.0
    return np.full(n_test, last)


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float).ravel()
    y_pred = np.asarray(y_pred, dtype=float).ravel()
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
