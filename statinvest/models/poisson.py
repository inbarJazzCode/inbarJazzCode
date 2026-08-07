"""Poisson regression for count outcomes (IRLS, log link, Poisson deviance).

Guards:
    * Outcomes are validated to be non-negative integers; continuous returns
      or prices are never silently reinterpreted as counts.
    * An optional exposure/offset term is supported with explicit validation.
    * Fitted means, deviance, Pearson residuals and an overdispersion
      diagnostic are reported; the user is warned when plain Poisson
      inference is unreliable (overdispersion / excess zeros).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from statinvest.models._util import (
    add_intercept,
    as_2d,
    check_finite,
    chi2_sf,
    normal_ppf,
    normal_sf,
)


@dataclass
class PoissonResult:
    params: np.ndarray
    feature_names: list[str]
    n: int
    k: int
    se: np.ndarray
    z_values: np.ndarray
    p_values: np.ndarray
    conf_int: np.ndarray
    converged: bool
    n_iter: int
    log_likelihood: float
    deviance: float
    pearson_chi2: float
    dispersion: float
    warnings: list[str] = field(default_factory=list)

    def coefficient_table(self) -> list[dict]:
        rows = []
        for i, name in enumerate(self.feature_names):
            rows.append(
                {
                    "term": name,
                    "coef": float(self.params[i]),
                    "rate_ratio": float(np.exp(self.params[i])),
                    "std_err": float(self.se[i]),
                    "z": float(self.z_values[i]),
                    "p_value": float(self.p_values[i]),
                    "ci_low": float(self.conf_int[i, 0]),
                    "ci_high": float(self.conf_int[i, 1]),
                }
            )
        return rows

    def summary(self) -> dict:
        return {
            "family": "poisson",
            "n": self.n,
            "k": self.k,
            "converged": self.converged,
            "n_iter": self.n_iter,
            "log_likelihood": self.log_likelihood,
            "deviance": self.deviance,
            "pearson_chi2": self.pearson_chi2,
            "dispersion": self.dispersion,
            "coefficients": self.coefficient_table(),
            "warnings": list(self.warnings),
        }


class PoissonModel:
    def __init__(self, fit_intercept: bool = True):
        self.fit_intercept = fit_intercept
        self._result: PoissonResult | None = None

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        exposure: np.ndarray | None = None,
        feature_names: list[str] | None = None,
        max_iter: int = 100,
        tol: float = 1e-8,
        alpha: float = 0.05,
    ) -> PoissonResult:
        X = as_2d(X)
        y = np.asarray(y, dtype=float).ravel()
        check_finite(X, y)
        if X.shape[0] != y.shape[0]:
            raise ValueError("X and y must have the same number of rows.")
        if np.any(y < 0):
            raise ValueError("Poisson outcomes must be non-negative.")
        if np.any(np.abs(y - np.round(y)) > 1e-9):
            raise ValueError(
                "Poisson outcomes must be integer counts; continuous values "
                "(e.g. returns or prices) must not be treated as counts."
            )

        offset = np.zeros_like(y)
        if exposure is not None:
            exposure = np.asarray(exposure, dtype=float).ravel()
            if exposure.shape[0] != y.shape[0]:
                raise ValueError("exposure must align with y.")
            if np.any(exposure <= 0):
                raise ValueError("exposure/offset values must be strictly positive.")
            offset = np.log(exposure)

        names = list(feature_names) if feature_names else [f"x{i+1}" for i in range(X.shape[1])]
        warnings: list[str] = []
        zero_frac = float(np.mean(y == 0))
        if zero_frac > 0.6:
            warnings.append(
                f"Excess zeros: {zero_frac:.0%} of counts are zero; consider a "
                "zero-inflated or hurdle model."
            )

        if self.fit_intercept:
            Xd = add_intercept(X)
            names = ["const"] + names
        else:
            Xd = X.copy()
        n, k = Xd.shape

        beta = np.zeros(k)
        # Sensible intercept start: log of mean rate.
        if self.fit_intercept:
            beta[0] = np.log(max(y.mean(), 1e-3))
        converged = False
        n_iter = 0
        H = None
        for n_iter in range(1, max_iter + 1):
            eta = Xd @ beta + offset
            mu = np.exp(np.clip(eta, -30, 30))
            W = mu
            grad = Xd.T @ (y - mu)
            H = Xd.T @ (Xd * W[:, None])
            try:
                step = np.linalg.solve(H, grad)
            except np.linalg.LinAlgError:
                step = np.linalg.lstsq(H, grad, rcond=None)[0]
            beta_new = beta + step
            if np.max(np.abs(step)) < tol:
                beta = beta_new
                converged = True
                break
            beta = beta_new

        if not converged:
            warnings.append(
                f"IRLS did not converge within {max_iter} iterations; "
                "results should not be treated as a valid fit."
            )

        try:
            cov = np.linalg.inv(H)
        except np.linalg.LinAlgError:
            cov = np.linalg.pinv(H)
        se = np.sqrt(np.clip(np.diag(cov), 0.0, None))
        with np.errstate(divide="ignore", invalid="ignore"):
            z_values = np.where(se > 0, beta / se, np.nan)
        p_values = np.array([normal_sf(z) * 2 if np.isfinite(z) else np.nan for z in z_values])
        zcrit = normal_ppf(1 - alpha / 2)
        conf = np.column_stack([beta - zcrit * se, beta + zcrit * se])

        mu = np.exp(np.clip(Xd @ beta + offset, -30, 30))
        # Poisson log-likelihood (dropping the constant log(y!) is fine for
        # comparisons, but we include it via lgamma for a proper value).
        from scipy.special import gammaln  # available; else Stirling

        ll = float(np.sum(y * np.log(np.clip(mu, 1e-12, None)) - mu - gammaln(y + 1)))
        # Deviance.
        with np.errstate(divide="ignore", invalid="ignore"):
            term = np.where(y > 0, y * np.log(y / mu), 0.0)
        deviance = float(2 * np.sum(term - (y - mu)))
        pearson = float(np.sum((y - mu) ** 2 / np.clip(mu, 1e-12, None)))
        df_resid = max(n - k, 1)
        dispersion = pearson / df_resid
        if dispersion > 1.5:
            warnings.append(
                f"Overdispersion detected (Pearson dispersion = {dispersion:.2f} > 1.5); "
                "plain Poisson standard errors are too small — consider "
                "quasi-Poisson or negative-binomial."
            )

        result = PoissonResult(
            params=beta,
            feature_names=names,
            n=n,
            k=k,
            se=se,
            z_values=z_values,
            p_values=p_values,
            conf_int=conf,
            converged=converged,
            n_iter=n_iter,
            log_likelihood=ll,
            deviance=deviance,
            pearson_chi2=pearson,
            dispersion=dispersion,
            warnings=warnings,
        )
        self._result = result
        self._beta = beta
        self.fit_intercept_offset_ = offset
        return result

    def predict(self, X: np.ndarray, exposure: np.ndarray | None = None) -> np.ndarray:
        self._require_fit()
        X = as_2d(X)
        Xd = add_intercept(X) if self.fit_intercept else X
        offset = np.zeros(X.shape[0])
        if exposure is not None:
            exposure = np.asarray(exposure, dtype=float).ravel()
            offset = np.log(exposure)
        return np.exp(np.clip(Xd @ self._beta + offset, -30, 30))

    def pearson_residuals(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        mu = self.predict(X)
        y = np.asarray(y, dtype=float).ravel()
        return (y - mu) / np.sqrt(np.clip(mu, 1e-12, None))

    def _require_fit(self) -> None:
        if self._result is None:
            raise RuntimeError("Model is not fitted.")
