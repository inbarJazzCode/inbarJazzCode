"""Small numerical helpers shared across model families."""

from __future__ import annotations

import numpy as np

# scipy is a hard dependency for accurate inferential p-values / quantiles, but
# we degrade gracefully to a normal approximation if it is unavailable so the
# core still runs.
try:  # pragma: no cover - exercised indirectly
    from scipy import stats as _sp_stats  # type: ignore

    _HAVE_SCIPY = True
except Exception:  # pragma: no cover
    _sp_stats = None
    _HAVE_SCIPY = False


def as_2d(x: np.ndarray) -> np.ndarray:
    """Return ``x`` as a 2-D float array (n, k)."""
    arr = np.asarray(x, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError(f"Expected 1-D or 2-D array, got shape {arr.shape}")
    return arr


def add_intercept(x: np.ndarray) -> np.ndarray:
    """Prepend a column of ones for the intercept term."""
    x = as_2d(x)
    return np.hstack([np.ones((x.shape[0], 1)), x])


def check_finite(*arrays: np.ndarray) -> None:
    for a in arrays:
        if not np.all(np.isfinite(a)):
            raise ValueError("Input contains non-finite values (NaN or inf).")


def design_condition_number(x: np.ndarray) -> float:
    """Condition number of the design matrix via singular values."""
    s = np.linalg.svd(x, compute_uv=False)
    smax = float(s[0]) if s.size else 0.0
    smin = float(s[-1]) if s.size else 0.0
    if smin <= 0:
        return float("inf")
    return smax / smin


def constant_columns(x: np.ndarray, exclude_intercept: bool = True) -> list[int]:
    """Indices of columns that are (numerically) constant."""
    cols = []
    start = 1 if exclude_intercept else 0
    for j in range(start, x.shape[1]):
        col = x[:, j]
        if np.ptp(col) <= 1e-12 * (1.0 + abs(float(np.mean(col)))):
            cols.append(j)
    return cols


def matrix_rank(x: np.ndarray) -> int:
    return int(np.linalg.matrix_rank(x))


def normal_ppf(q: float) -> float:
    """Inverse standard-normal CDF."""
    if _HAVE_SCIPY:
        return float(_sp_stats.norm.ppf(q))
    # Acklam's rational approximation (accurate to ~1e-9).
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if q < plow:
        r = np.sqrt(-2 * np.log(q))
        return (((((c[0]*r+c[1])*r+c[2])*r+c[3])*r+c[4])*r+c[5]) / \
               ((((d[0]*r+d[1])*r+d[2])*r+d[3])*r+1)
    if q > phigh:
        r = np.sqrt(-2 * np.log(1 - q))
        return -(((((c[0]*r+c[1])*r+c[2])*r+c[3])*r+c[4])*r+c[5]) / \
               ((((d[0]*r+d[1])*r+d[2])*r+d[3])*r+1)
    r = q - 0.5
    s = r * r
    return (((((a[0]*s+a[1])*s+a[2])*s+a[3])*s+a[4])*s+a[5])*r / \
           (((((b[0]*s+b[1])*s+b[2])*s+b[3])*s+b[4])*s+1)


def t_ppf(q: float, df: float) -> float:
    if _HAVE_SCIPY:
        return float(_sp_stats.t.ppf(q, df))
    return normal_ppf(q)  # large-sample fallback


def normal_sf(z: float) -> float:
    """Two-sided-friendly upper-tail probability of |Z|."""
    if _HAVE_SCIPY:
        return float(_sp_stats.norm.sf(abs(z)))
    from math import erfc, sqrt
    return 0.5 * erfc(abs(z) / sqrt(2.0))


def t_sf(t: float, df: float) -> float:
    if _HAVE_SCIPY:
        return float(_sp_stats.t.sf(abs(t), df))
    return normal_sf(t)


def chi2_sf(x: float, df: float) -> float:
    if _HAVE_SCIPY:
        return float(_sp_stats.chi2.sf(x, df))
    # Wilson-Hilferty approximation.
    if x <= 0:
        return 1.0
    z = ((x / df) ** (1.0 / 3.0) - (1 - 2.0 / (9 * df))) / np.sqrt(2.0 / (9 * df))
    return normal_sf(z) if z >= 0 else 1 - normal_sf(z)
