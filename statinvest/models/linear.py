"""OLS / linear regression with a numerically stable solver and diagnostics.

Design decisions:
    * The default solver is a QR / least-squares decomposition
      (``numpy.linalg.lstsq``), **not** an explicit ``(X'X)^-1`` inverse.
    * Rank deficiency, perfect multicollinearity, constant columns, tiny
      samples and ill-conditioning are detected and surfaced as warnings.
    * Classical and heteroskedasticity-consistent (HC0/HC1/HC3) standard
      errors are available; inferential output is kept separate from
      predictive performance metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from statinvest.models._util import (
    add_intercept,
    as_2d,
    check_finite,
    constant_columns,
    design_condition_number,
    matrix_rank,
    t_ppf,
    t_sf,
)


@dataclass
class OLSResult:
    """Container for a fitted OLS model."""

    params: np.ndarray
    feature_names: list[str]
    n: int
    k: int
    df_resid: int
    se: np.ndarray
    se_type: str
    t_values: np.ndarray
    p_values: np.ndarray
    conf_int: np.ndarray  # (k, 2)
    r_squared: float
    adj_r_squared: float
    sigma2: float          # residual variance estimate
    rmse: float
    aic: float
    bic: float
    condition_number: float
    rank: int
    warnings: list[str] = field(default_factory=list)

    def coefficient_table(self) -> list[dict]:
        rows = []
        for i, name in enumerate(self.feature_names):
            rows.append(
                {
                    "term": name,
                    "coef": float(self.params[i]),
                    "std_err": float(self.se[i]),
                    "t": float(self.t_values[i]),
                    "p_value": float(self.p_values[i]),
                    "ci_low": float(self.conf_int[i, 0]),
                    "ci_high": float(self.conf_int[i, 1]),
                }
            )
        return rows

    def summary(self) -> dict:
        return {
            "family": "ols",
            "n": self.n,
            "k": self.k,
            "df_resid": self.df_resid,
            "se_type": self.se_type,
            "r_squared": self.r_squared,
            "adj_r_squared": self.adj_r_squared,
            "rmse": self.rmse,
            "sigma2": self.sigma2,
            "aic": self.aic,
            "bic": self.bic,
            "condition_number": self.condition_number,
            "rank": self.rank,
            "coefficients": self.coefficient_table(),
            "warnings": list(self.warnings),
        }


class OLSModel:
    """Ordinary least squares estimated with a stable QR/SVD solver."""

    def __init__(self, fit_intercept: bool = True):
        self.fit_intercept = fit_intercept
        self._result: OLSResult | None = None
        self._X: np.ndarray | None = None
        self._y: np.ndarray | None = None

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str] | None = None,
        se_type: str = "classical",
        alpha: float = 0.05,
    ) -> OLSResult:
        X = as_2d(X)
        y = np.asarray(y, dtype=float).ravel()
        check_finite(X, y)
        if X.shape[0] != y.shape[0]:
            raise ValueError("X and y must have the same number of rows.")

        names = list(feature_names) if feature_names else [f"x{i+1}" for i in range(X.shape[1])]
        if len(names) != X.shape[1]:
            raise ValueError("feature_names length must match number of columns.")

        warnings: list[str] = []
        if self.fit_intercept:
            Xd = add_intercept(X)
            names = ["const"] + names
        else:
            Xd = X.copy()

        n, k = Xd.shape
        if n <= k:
            warnings.append(
                f"Tiny sample: n={n} observations for k={k} parameters; "
                "inference is unreliable or undefined."
            )
        rank = matrix_rank(Xd)
        if rank < k:
            warnings.append(
                f"Rank-deficient design (rank {rank} < {k} columns): perfect "
                "multicollinearity or redundant features present."
            )
        const_cols = constant_columns(Xd)
        for j in const_cols:
            warnings.append(f"Column '{names[j]}' is constant (aside from intercept).")
        cond = design_condition_number(Xd)
        if np.isfinite(cond) and cond > 1e4:
            warnings.append(
                f"Ill-conditioned design (condition number ~ {cond:.3g}); "
                "coefficients may be numerically unstable."
            )

        # Stable least-squares solve (QR/SVD internally), no explicit inverse.
        beta, _, _, _ = np.linalg.lstsq(Xd, y, rcond=None)

        fitted = Xd @ beta
        resid = y - fitted
        df_resid = max(n - rank, 0)
        rss = float(resid @ resid)
        sigma2 = rss / df_resid if df_resid > 0 else float("nan")
        tss = float(((y - y.mean()) ** 2).sum())
        r2 = 1.0 - rss / tss if tss > 0 else float("nan")
        adj_r2 = (
            1.0 - (1.0 - r2) * (n - 1) / df_resid
            if df_resid > 0 and np.isfinite(r2)
            else float("nan")
        )
        rmse = float(np.sqrt(rss / n))

        # Covariance of the coefficients. Use the pseudo-inverse of X'X derived
        # from the SVD of Xd for numerical stability (still not a naive inverse
        # of a possibly singular matrix).
        cov = self._coef_covariance(Xd, resid, sigma2, se_type)
        se = np.sqrt(np.clip(np.diag(cov), 0.0, None))

        with np.errstate(divide="ignore", invalid="ignore"):
            t_values = np.where(se > 0, beta / se, np.nan)
        p_values = np.array(
            [t_sf(t, df_resid) * 2 if np.isfinite(t) and df_resid > 0 else np.nan for t in t_values]
        )
        tcrit = t_ppf(1 - alpha / 2, df_resid) if df_resid > 0 else np.nan
        conf = np.column_stack([beta - tcrit * se, beta + tcrit * se])

        # Log-likelihood under normality for AIC/BIC.
        if df_resid > 0 and rss > 0:
            ll = -0.5 * n * (np.log(2 * np.pi) + np.log(rss / n) + 1)
            aic = 2 * k - 2 * ll
            bic = k * np.log(n) - 2 * ll
        else:
            aic = bic = float("nan")

        result = OLSResult(
            params=beta,
            feature_names=names,
            n=n,
            k=k,
            df_resid=df_resid,
            se=se,
            se_type=se_type,
            t_values=t_values,
            p_values=p_values,
            conf_int=conf,
            r_squared=r2,
            adj_r_squared=adj_r2,
            sigma2=sigma2,
            rmse=rmse,
            aic=aic,
            bic=bic,
            condition_number=cond,
            rank=rank,
            warnings=warnings,
        )
        self._result = result
        self._X, self._y = Xd, y
        return result

    @staticmethod
    def _coef_covariance(
        Xd: np.ndarray, resid: np.ndarray, sigma2: float, se_type: str
    ) -> np.ndarray:
        # (X'X)^+ via SVD.
        XtX = Xd.T @ Xd
        XtX_pinv = np.linalg.pinv(XtX)
        se_type = se_type.lower()
        if se_type == "classical":
            return sigma2 * XtX_pinv
        # Heteroskedasticity-consistent (sandwich) estimators.
        n, k = Xd.shape
        h = np.einsum("ij,jk,ik->i", Xd, XtX_pinv, Xd)  # leverages
        u2 = resid ** 2
        if se_type == "hc0":
            omega = u2
        elif se_type == "hc1":
            omega = u2 * (n / max(n - k, 1))
        elif se_type == "hc3":
            omega = u2 / np.clip((1 - h) ** 2, 1e-12, None)
        else:
            raise ValueError(f"Unknown se_type '{se_type}'. Use classical/hc0/hc1/hc3.")
        meat = (Xd * omega[:, None]).T @ Xd
        return XtX_pinv @ meat @ XtX_pinv

    # -- diagnostics ---------------------------------------------------------
    def predict(self, X: np.ndarray) -> np.ndarray:
        if self._result is None:
            raise RuntimeError("Model is not fitted.")
        X = as_2d(X)
        Xd = add_intercept(X) if self.fit_intercept else X
        return Xd @ self._result.params

    def residuals(self) -> np.ndarray:
        self._require_fit()
        return self._y - self._X @ self._result.params

    def fitted_values(self) -> np.ndarray:
        self._require_fit()
        return self._X @ self._result.params

    def leverage(self) -> np.ndarray:
        """Diagonal of the hat matrix (leverage values)."""
        self._require_fit()
        Xd = self._X
        XtX_pinv = np.linalg.pinv(Xd.T @ Xd)
        return np.einsum("ij,jk,ik->i", Xd, XtX_pinv, Xd)

    def cooks_distance(self) -> np.ndarray:
        """Cook's distance influence measure per observation."""
        self._require_fit()
        r = self.residuals()
        h = self.leverage()
        s2 = self._result.sigma2
        k = self._result.k
        with np.errstate(divide="ignore", invalid="ignore"):
            std_resid2 = (r ** 2) / (s2 * np.clip(1 - h, 1e-12, None))
            return (std_resid2 / k) * (h / np.clip(1 - h, 1e-12, None))

    def variance_inflation_factors(self) -> dict[str, float]:
        """VIF per non-intercept feature (multicollinearity diagnostic)."""
        self._require_fit()
        Xd = self._X
        names = self._result.feature_names
        start = 1 if self.fit_intercept else 0
        vifs: dict[str, float] = {}
        for j in range(start, Xd.shape[1]):
            others = np.delete(Xd, j, axis=1)
            target = Xd[:, j]
            beta, _, _, _ = np.linalg.lstsq(others, target, rcond=None)
            pred = others @ beta
            ss_res = float(((target - pred) ** 2).sum())
            ss_tot = float(((target - target.mean()) ** 2).sum())
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
            vifs[names[j]] = float("inf") if r2 >= 1 else 1.0 / (1.0 - r2)
        return vifs

    def breusch_pagan(self) -> dict:
        """Breusch-Pagan test for heteroskedasticity."""
        self._require_fit()
        r = self.residuals()
        Xd = self._X
        n = len(r)
        g = r ** 2 / (float(r @ r) / n)
        beta, _, _, _ = np.linalg.lstsq(Xd, g, rcond=None)
        pred = Xd @ beta
        ss_reg = float(((pred - g.mean()) ** 2).sum())
        lm = ss_reg / 2.0
        from statinvest.models._util import chi2_sf

        df = Xd.shape[1] - 1
        return {"statistic": lm, "df": df, "p_value": chi2_sf(lm, df)}

    def _require_fit(self) -> None:
        if self._result is None or self._X is None or self._y is None:
            raise RuntimeError("Model is not fitted.")
