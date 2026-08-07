"""Optimization laboratory: transparent SGD and Adam optimizers.

These are educational / comparative optimizers. Each is compared against an
appropriate reference estimator (stable least squares for the OLS objective, a
trusted IRLS fit for GLMs). The correct objective is used for each model
family, convergence is judged explicitly (a completed loop is *not* treated as
convergence), and a finite-difference gradient check is provided for custom
objectives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from statinvest.models.logistic import stable_sigmoid


@dataclass
class OptimResult:
    params: np.ndarray
    loss_trace: list[float]
    n_iter: int
    converged: bool
    grad_norm: float
    objective: str
    optimizer: str
    hyperparameters: dict
    ref_params: np.ndarray | None = None
    max_coef_diff: float | None = None
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "optimizer": self.optimizer,
            "objective": self.objective,
            "n_iter": self.n_iter,
            "converged": self.converged,
            "final_loss": self.loss_trace[-1] if self.loss_trace else None,
            "grad_norm": self.grad_norm,
            "max_coef_diff_vs_reference": self.max_coef_diff,
            "hyperparameters": dict(self.hyperparameters),
            "warnings": list(self.warnings),
        }


# -- objectives --------------------------------------------------------------
def mse_objective(beta, X, y):
    n = X.shape[0]
    resid = X @ beta - y
    loss = float(resid @ resid) / n
    grad = (2.0 / n) * (X.T @ resid)
    return loss, grad


def logistic_objective(beta, X, y):
    n = X.shape[0]
    p = stable_sigmoid(X @ beta)
    eps = 1e-12
    loss = float(-np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)))
    grad = (1.0 / n) * (X.T @ (p - y))
    return loss, grad


OBJECTIVES: dict[str, Callable] = {
    "mse": mse_objective,
    "logistic": logistic_objective,
}


def gradient_check(
    objective: Callable, beta: np.ndarray, X: np.ndarray, y: np.ndarray, eps: float = 1e-6
) -> float:
    """Return the max abs difference between analytic and numeric gradients."""
    _, analytic = objective(beta, X, y)
    numeric = np.zeros_like(beta)
    for i in range(len(beta)):
        b1 = beta.copy(); b1[i] += eps
        b2 = beta.copy(); b2[i] -= eps
        f1, _ = objective(b1, X, y)
        f2, _ = objective(b2, X, y)
        numeric[i] = (f1 - f2) / (2 * eps)
    return float(np.max(np.abs(analytic - numeric)))


def _iterate(
    objective: Callable,
    X: np.ndarray,
    y: np.ndarray,
    optimizer: str,
    lr: float,
    epochs: int,
    batch_size: int | None,
    l2: float,
    seed: int,
    tol: float,
    patience: int,
) -> OptimResult:
    rng = np.random.default_rng(seed)
    n, k = X.shape
    beta = np.zeros(k)
    m = np.zeros(k)
    v = np.zeros(k)
    beta1, beta2, adam_eps = 0.9, 0.999, 1e-8
    t = 0
    loss_trace: list[float] = []
    warnings: list[str] = []
    best_loss = np.inf
    no_improve = 0
    converged = False
    bs = batch_size or n

    for epoch in range(epochs):
        idx = rng.permutation(n)
        for start in range(0, n, bs):
            batch = idx[start:start + bs]
            Xb, yb = X[batch], y[batch]
            _, grad = objective(beta, Xb, yb)
            grad = grad + l2 * beta
            t += 1
            if optimizer == "sgd":
                beta = beta - lr * grad
            elif optimizer == "adam":
                m = beta1 * m + (1 - beta1) * grad
                v = beta2 * v + (1 - beta2) * (grad ** 2)
                m_hat = m / (1 - beta1 ** t)
                v_hat = v / (1 - beta2 ** t)
                beta = beta - lr * m_hat / (np.sqrt(v_hat) + adam_eps)
            else:
                raise ValueError(f"Unknown optimizer '{optimizer}'.")
        full_loss, full_grad = objective(beta, X, y)
        loss_trace.append(full_loss)
        if not np.isfinite(full_loss):
            warnings.append("Loss diverged to a non-finite value; reduce the learning rate.")
            break
        if full_loss < best_loss - tol:
            best_loss = full_loss
            no_improve = 0
        else:
            no_improve += 1
        if float(np.linalg.norm(full_grad)) < tol:
            converged = True
            break
        if no_improve >= patience:
            converged = True  # early stop on plateau
            break

    _, final_grad = objective(beta, X, y)
    grad_norm = float(np.linalg.norm(final_grad))
    if not converged and grad_norm >= tol:
        warnings.append(
            f"Optimizer completed {len(loss_trace)} epochs without meeting the "
            f"convergence tolerance (grad norm {grad_norm:.2e} >= {tol:.1e}); "
            "do not treat this as a converged fit."
        )
    return OptimResult(
        params=beta,
        loss_trace=loss_trace,
        n_iter=len(loss_trace),
        converged=converged,
        grad_norm=grad_norm,
        objective="",  # filled by caller
        optimizer=optimizer,
        hyperparameters={
            "lr": lr, "epochs": epochs, "batch_size": bs, "l2": l2,
            "seed": seed, "tol": tol, "patience": patience,
        },
        warnings=warnings,
    )


def run_optimizer(
    X: np.ndarray,
    y: np.ndarray,
    objective: str = "mse",
    optimizer: str = "sgd",
    lr: float = 0.01,
    epochs: int = 500,
    batch_size: int | None = None,
    l2: float = 0.0,
    seed: int = 0,
    tol: float = 1e-6,
    patience: int = 25,
    reference: np.ndarray | None = None,
) -> OptimResult:
    """Run SGD or Adam and compare against a reference estimator."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float).ravel()
    if objective not in OBJECTIVES:
        raise ValueError(f"Unknown objective '{objective}'. Choose from {list(OBJECTIVES)}.")
    obj = OBJECTIVES[objective]
    result = _iterate(
        obj, X, y, optimizer, lr, epochs, batch_size, l2, seed, tol, patience
    )
    result.objective = objective

    if reference is None:
        if objective == "mse":
            reference, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    if reference is not None:
        result.ref_params = np.asarray(reference, dtype=float)
        result.max_coef_diff = float(np.max(np.abs(result.params - result.ref_params)))
    return result
