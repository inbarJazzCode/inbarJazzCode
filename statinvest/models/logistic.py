"""Binary logistic regression estimated with IRLS (Newton) and a stable
log-loss / binomial likelihood.

Guards:
    * The target is validated to be binary; the encoded classes are recorded.
    * A numerically stable ``log(1 + exp(-|z|))`` formulation avoids overflow.
    * Complete / quasi-complete separation, severe class imbalance and
      non-convergence are detected and surfaced.
    * Classification metrics (confusion matrix, precision, recall, F1, ROC-AUC,
      PR-AUC) are reported separately from the likelihood-based fit.
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


def stable_sigmoid(z: np.ndarray) -> np.ndarray:
    """Numerically stable logistic sigmoid."""
    z = np.asarray(z, dtype=float)
    out = np.empty_like(z)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    ez = np.exp(z[~pos])
    out[~pos] = ez / (1.0 + ez)
    return out


def log_loss(y: np.ndarray, p: np.ndarray, eps: float = 1e-12) -> float:
    p = np.clip(p, eps, 1 - eps)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


@dataclass
class LogisticResult:
    params: np.ndarray
    feature_names: list[str]
    classes_: tuple
    n: int
    k: int
    se: np.ndarray
    z_values: np.ndarray
    p_values: np.ndarray
    conf_int: np.ndarray
    converged: bool
    n_iter: int
    log_likelihood: float
    null_log_likelihood: float
    deviance: float
    pseudo_r2_mcfadden: float
    lr_stat: float
    lr_p_value: float
    warnings: list[str] = field(default_factory=list)

    def coefficient_table(self) -> list[dict]:
        rows = []
        for i, name in enumerate(self.feature_names):
            rows.append(
                {
                    "term": name,
                    "coef": float(self.params[i]),
                    "odds_ratio": float(np.exp(self.params[i])),
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
            "family": "logistic",
            "classes": list(self.classes_),
            "n": self.n,
            "k": self.k,
            "converged": self.converged,
            "n_iter": self.n_iter,
            "log_likelihood": self.log_likelihood,
            "deviance": self.deviance,
            "pseudo_r2_mcfadden": self.pseudo_r2_mcfadden,
            "lr_stat": self.lr_stat,
            "lr_p_value": self.lr_p_value,
            "coefficients": self.coefficient_table(),
            "warnings": list(self.warnings),
        }


class LogisticModel:
    def __init__(self, fit_intercept: bool = True, l2: float = 0.0):
        self.fit_intercept = fit_intercept
        self.l2 = float(l2)
        self._result: LogisticResult | None = None

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str] | None = None,
        max_iter: int = 100,
        tol: float = 1e-8,
        alpha: float = 0.05,
    ) -> LogisticResult:
        X = as_2d(X)
        y_raw = np.asarray(y).ravel()
        check_finite(X)
        if X.shape[0] != y_raw.shape[0]:
            raise ValueError("X and y must have the same number of rows.")

        classes = tuple(sorted(np.unique(y_raw).tolist()))
        if len(classes) != 2:
            raise ValueError(
                f"Binary logistic regression requires exactly 2 classes; got {classes}."
            )
        # Encode: the larger class label -> 1 (documented in classes_).
        y = (y_raw == classes[1]).astype(float)

        names = list(feature_names) if feature_names else [f"x{i+1}" for i in range(X.shape[1])]
        warnings: list[str] = []
        pos_rate = float(y.mean())
        if pos_rate < 0.05 or pos_rate > 0.95:
            warnings.append(
                f"Severe class imbalance: positive rate = {pos_rate:.3f}; "
                "metrics and inference may be unstable."
            )

        if self.fit_intercept:
            Xd = add_intercept(X)
            names = ["const"] + names
        else:
            Xd = X.copy()
        n, k = Xd.shape

        beta = np.zeros(k)
        converged = False
        n_iter = 0
        last_cov = None
        for n_iter in range(1, max_iter + 1):
            eta = Xd @ beta
            p = stable_sigmoid(eta)
            W = np.clip(p * (1 - p), 1e-9, None)
            # Ridge on non-intercept terms only.
            reg = self.l2 * np.eye(k)
            if self.fit_intercept:
                reg[0, 0] = 0.0
            grad = Xd.T @ (y - p) - self.l2 * _mask_intercept(beta, self.fit_intercept)
            H = Xd.T @ (Xd * W[:, None]) + reg
            try:
                step = np.linalg.solve(H, grad)
            except np.linalg.LinAlgError:
                step = np.linalg.lstsq(H, grad, rcond=None)[0]
                warnings.append("Hessian near-singular; used least-squares Newton step.")
            beta_new = beta + step
            last_cov = H
            if np.max(np.abs(step)) < tol:
                beta = beta_new
                converged = True
                break
            beta = beta_new

        max_abs = float(np.max(np.abs(beta)))
        if max_abs > 25:
            warnings.append(
                "Very large coefficients detected: possible complete or "
                "quasi-complete separation; probabilities may be degenerate."
            )
        if not converged:
            warnings.append(
                f"IRLS did not converge within {max_iter} iterations; "
                "results should not be treated as a valid fit."
            )

        # Covariance from the final (regularized) Hessian.
        try:
            cov = np.linalg.inv(last_cov)
        except np.linalg.LinAlgError:
            cov = np.linalg.pinv(last_cov)
        se = np.sqrt(np.clip(np.diag(cov), 0.0, None))
        with np.errstate(divide="ignore", invalid="ignore"):
            z_values = np.where(se > 0, beta / se, np.nan)
        p_values = np.array([normal_sf(z) * 2 if np.isfinite(z) else np.nan for z in z_values])
        zcrit = normal_ppf(1 - alpha / 2)
        conf = np.column_stack([beta - zcrit * se, beta + zcrit * se])

        p_hat = stable_sigmoid(Xd @ beta)
        ll = -log_loss(y, p_hat) * n
        p0 = np.clip(y.mean(), 1e-12, 1 - 1e-12)
        null_ll = n * (p0 * np.log(p0) + (1 - p0) * np.log(1 - p0))
        deviance = -2 * ll
        mcf = 1 - ll / null_ll if null_ll != 0 else float("nan")
        lr_stat = 2 * (ll - null_ll)
        lr_p = chi2_sf(lr_stat, max(k - (1 if self.fit_intercept else 0), 1))

        result = LogisticResult(
            params=beta,
            feature_names=names,
            classes_=classes,
            n=n,
            k=k,
            se=se,
            z_values=z_values,
            p_values=p_values,
            conf_int=conf,
            converged=converged,
            n_iter=n_iter,
            log_likelihood=ll,
            null_log_likelihood=null_ll,
            deviance=deviance,
            pseudo_r2_mcfadden=mcf,
            lr_stat=lr_stat,
            lr_p_value=lr_p,
            warnings=warnings,
        )
        self._result = result
        self._beta = beta
        self._classes = classes
        return result

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        self._require_fit()
        X = as_2d(X)
        Xd = add_intercept(X) if self.fit_intercept else X
        return stable_sigmoid(Xd @ self._beta)

    def predict(self, X: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        proba = self.predict_proba(X)
        pos = (proba >= threshold)
        return np.where(pos, self._classes[1], self._classes[0])

    def classification_metrics(
        self, X: np.ndarray, y: np.ndarray, threshold: float = 0.5
    ) -> dict:
        self._require_fit()
        y_raw = np.asarray(y).ravel()
        y_bin = (y_raw == self._classes[1]).astype(int)
        proba = self.predict_proba(X)
        pred = (proba >= threshold).astype(int)
        tp = int(np.sum((pred == 1) & (y_bin == 1)))
        tn = int(np.sum((pred == 0) & (y_bin == 0)))
        fp = int(np.sum((pred == 1) & (y_bin == 0)))
        fn = int(np.sum((pred == 0) & (y_bin == 1)))
        precision = tp / (tp + fp) if (tp + fp) else float("nan")
        recall = tp / (tp + fn) if (tp + fn) else float("nan")
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision and recall and np.isfinite(precision) and np.isfinite(recall)
            else float("nan")
        )
        accuracy = (tp + tn) / len(y_bin)
        return {
            "threshold": threshold,
            "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "roc_auc": roc_auc(y_bin, proba),
            "pr_auc": pr_auc(y_bin, proba),
            "brier_score": float(np.mean((proba - y_bin) ** 2)),
        }

    def _require_fit(self) -> None:
        if self._result is None:
            raise RuntimeError("Model is not fitted.")


def _mask_intercept(beta: np.ndarray, fit_intercept: bool) -> np.ndarray:
    if not fit_intercept:
        return beta
    masked = beta.copy()
    masked[0] = 0.0
    return masked


def roc_auc(y: np.ndarray, scores: np.ndarray) -> float:
    """ROC-AUC via the rank (Mann-Whitney U) statistic; handles ties."""
    y = np.asarray(y).ravel()
    n_pos = int(np.sum(y == 1))
    n_neg = int(np.sum(y == 0))
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=float)
    s = scores[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # average rank (1-based)
        ranks[order[i:j + 1]] = avg
        i = j + 1
    sum_pos = float(np.sum(ranks[y == 1]))
    return (sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def pr_auc(y: np.ndarray, scores: np.ndarray) -> float:
    """Average precision (area under the precision-recall curve)."""
    y = np.asarray(y).ravel()
    if np.sum(y == 1) == 0:
        return float("nan")
    order = np.argsort(-scores, kind="mergesort")
    y_sorted = y[order]
    tp = np.cumsum(y_sorted == 1)
    fp = np.cumsum(y_sorted == 0)
    precision = tp / np.clip(tp + fp, 1, None)
    total_pos = np.sum(y == 1)
    recall = tp / total_pos
    ap = 0.0
    prev_recall = 0.0
    for i in range(len(y_sorted)):
        if i == 0 or recall[i] != prev_recall:
            ap += precision[i] * (recall[i] - prev_recall)
            prev_recall = recall[i]
    return float(ap)
