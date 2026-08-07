# STATISTICAL VALIDATION

Every claim below is backed by a deterministic test using synthetic data with
known parameters (see `tests/`).

## OLS / linear regression
- **Solver:** `numpy.linalg.lstsq` (QR/SVD internally) — no explicit `(X'X)^-1`.
  Coefficient covariance uses the SVD-based pseudo-inverse of `X'X`.
- **Coefficient recovery:** recovered `[4.0, 1.5, -2.0, 0.7]` within ±0.1 on
  n=500 (`test_ols_coefficient_recovery`).
- **Ill-posed detection:** rank-deficiency/perfect collinearity, constant
  columns, tiny samples and high condition numbers each raise explicit warnings
  (`test_ols_singular_design_warns`, `test_ols_constant_column_detected`,
  `test_ols_tiny_sample_warns`).
- **Robust SE:** HC0/HC1/HC3 sandwich estimators differ from classical SE under
  heteroskedasticity (`test_ols_robust_se_differs_under_heteroskedasticity`).
- **Diagnostics:** VIF, Cook's distance, leverage, Breusch-Pagan.

## Binary logistic regression
- **Estimator:** IRLS (Newton) with a numerically stable sigmoid
  (`test_stable_sigmoid_no_overflow`: no overflow at ±1000).
- **Objective:** binomial log-loss — never OLS MSE.
- **Recovery/convergence:** correct coefficient signs and convergence on n=600
  (`test_logistic_recovers_signs_and_converges`).
- **Guards:** non-binary target rejected; complete separation and severe class
  imbalance warned (`test_logistic_rejects_non_binary`,
  `test_logistic_separation_warns`, `test_logistic_class_imbalance_warns`).
- **Metrics:** ROC-AUC (rank statistic, tie-safe) and PR-AUC validated on
  perfect/random scores (`test_roc_auc_perfect_and_random`).

## Poisson regression
- **Estimator:** IRLS with log link and Poisson deviance.
- **Recovery:** intercept and slope recovered within ±0.15 (`test_poisson_recovers_rate`).
- **Validation:** non-integer and negative outcomes rejected; continuous
  returns/prices are never treated as counts (`test_poisson_rejects_non_integer`,
  `test_poisson_rejects_negative`).
- **Offset/exposure:** supported and validated positive (`test_poisson_offset_supported`,
  `test_poisson_offset_requires_positive`).
- **Overdispersion / excess zeros:** warned via Pearson dispersion and zero
  fraction (`test_poisson_overdispersion_warns`, `test_poisson_excess_zeros_warns`).

## Optimization laboratory
- SGD and Adam use the correct objective per family; Adam matches the
  least-squares reference within 0.05 (`test_optimizer_matches_reference`).
- Runs are reproducible under a fixed seed (`test_optimizer_reproducible`).
- Non-convergence/divergence is flagged, never presented as a valid fit
  (`test_optimizer_nonconvergence_flagged`).
- Analytic gradients match finite differences to < 1e-5
  (`test_gradient_check_mse_and_logistic`).

## Transformations & evaluation
- `safe_log` rejects non-positive values before any logarithm
  (`test_safe_log_rejects_nonpositive`).
- Chronological and walk-forward splits are leakage-free: every train index
  precedes every validation/test index (`test_chronological_split_no_leakage`,
  `test_walk_forward_windows_increasing`).
- Runs serialize to JSON (never pickle) and refuse secret-like keys
  (`test_serialize_run_no_secrets`).

## Known statistical limitations
See `KNOWN_LIMITATIONS.md`.
