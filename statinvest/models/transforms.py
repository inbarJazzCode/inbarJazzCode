"""Auditable transformations and model specification.

Supports level-level, log-level, level-log and log-log specifications, plus
standardization, interactions and selected polynomial terms — always with an
explicit, inspectable description of what was applied. Zero and negative values
are rejected (or explicitly handled) before any logarithm.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


class TransformError(ValueError):
    """Raised when a transformation is mathematically invalid for the data."""


def safe_log(values: np.ndarray, name: str = "value") -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if np.any(values <= 0):
        n_bad = int(np.sum(values <= 0))
        raise TransformError(
            f"Cannot log-transform '{name}': {n_bad} value(s) are <= 0. "
            "Filter, shift, or choose a level specification instead."
        )
    return np.log(values)


@dataclass
class Standardizer:
    """Fit-on-train standardizer to avoid leakage."""

    mean_: np.ndarray | None = None
    std_: np.ndarray | None = None

    def fit(self, X: np.ndarray) -> "Standardizer":
        X = np.asarray(X, dtype=float)
        self.mean_ = X.mean(axis=0)
        std = X.std(axis=0, ddof=0)
        self.std_ = np.where(std > 0, std, 1.0)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.mean_ is None or self.std_ is None:
            raise RuntimeError("Standardizer is not fitted.")
        return (np.asarray(X, dtype=float) - self.mean_) / self.std_

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        return self.fit(X).transform(X)


@dataclass
class Specification:
    """A fully auditable description of a fitted model's inputs."""

    family: str
    target: str
    features: list[str]
    target_transform: str = "level"        # level | log
    feature_transforms: dict = field(default_factory=dict)  # name -> level|log
    standardize: bool = False
    interactions: list[tuple[str, str]] = field(default_factory=list)
    polynomials: dict = field(default_factory=dict)  # name -> degree
    n_observations: int = 0
    n_dropped: int = 0
    missing_policy: str = "drop-rows-with-any-missing"
    formula: str = ""

    def describe(self) -> dict:
        return {
            "family": self.family,
            "target": self.target,
            "features": list(self.features),
            "target_transform": self.target_transform,
            "feature_transforms": dict(self.feature_transforms),
            "standardize": self.standardize,
            "interactions": [list(p) for p in self.interactions],
            "polynomials": dict(self.polynomials),
            "n_observations": self.n_observations,
            "n_dropped": self.n_dropped,
            "missing_policy": self.missing_policy,
            "formula": self.formula,
        }


def build_design(
    data: dict[str, np.ndarray],
    spec: Specification,
    standardizer: Standardizer | None = None,
) -> tuple[np.ndarray, np.ndarray, list[str], Specification]:
    """Construct (y, X, feature_names, resolved_spec) from a column dict.

    ``data`` maps column name -> 1-D array. Rows with any missing (NaN) value in
    the target or a used feature are dropped, and the count is recorded.
    """
    cols = {}
    for name in [spec.target, *spec.features]:
        if name not in data:
            raise KeyError(f"Column '{name}' not present in data.")
        cols[name] = np.asarray(data[name], dtype=float)

    n0 = len(cols[spec.target])
    mask = np.ones(n0, dtype=bool)
    for arr in cols.values():
        mask &= np.isfinite(arr)
    n_dropped = int(np.sum(~mask))

    y_raw = cols[spec.target][mask]
    if spec.target_transform == "log":
        y = safe_log(y_raw, spec.target)
    else:
        y = y_raw

    feature_arrays = []
    feature_names: list[str] = []
    for name in spec.features:
        col = cols[name][mask]
        tr = spec.feature_transforms.get(name, "level")
        if tr == "log":
            col = safe_log(col, name)
            disp = f"log({name})"
        else:
            disp = name
        feature_arrays.append(col)
        feature_names.append(disp)

    X = np.column_stack(feature_arrays) if feature_arrays else np.empty((len(y), 0))

    # Polynomials.
    for name, degree in spec.polynomials.items():
        if name not in spec.features:
            raise KeyError(f"Polynomial base '{name}' must be a feature.")
        idx = spec.features.index(name)
        base = X[:, idx]
        for d in range(2, int(degree) + 1):
            X = np.column_stack([X, base ** d])
            feature_names.append(f"{feature_names[idx]}^{d}")

    # Interactions.
    for a, b in spec.interactions:
        ia, ib = feature_names.index(_disp(a, spec)), feature_names.index(_disp(b, spec))
        X = np.column_stack([X, X[:, ia] * X[:, ib]])
        feature_names.append(f"{feature_names[ia]}*{feature_names[ib]}")

    if spec.standardize and X.shape[1] > 0:
        if standardizer is None:
            standardizer = Standardizer().fit(X)
        X = standardizer.transform(X)

    resolved = Specification(**{**spec.describe(), "family": spec.family})
    resolved.n_observations = len(y)
    resolved.n_dropped = n_dropped
    resolved.formula = _formula(spec, feature_names)
    return y, X, feature_names, resolved


def _disp(name: str, spec: Specification) -> str:
    tr = spec.feature_transforms.get(name, "level")
    return f"log({name})" if tr == "log" else name


def _formula(spec: Specification, feature_names: list[str]) -> str:
    lhs = f"log({spec.target})" if spec.target_transform == "log" else spec.target
    rhs = " + ".join(["const", *feature_names]) if feature_names else "const"
    return f"{lhs} ~ {rhs}"
