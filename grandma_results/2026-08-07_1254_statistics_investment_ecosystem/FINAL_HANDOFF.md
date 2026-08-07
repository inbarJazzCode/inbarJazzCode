# FINAL HANDOFF — Statistics & Investment Eco-System

**Run:** 2026-08-07_1254 · **Branch:** `claude/new-session-z4iq3g`

## What was delivered

An important reality-check first: **the repository was empty** at the start of
this run (no files, no commits; the remote had no refs). The prompt was written
for an existing "TA125 StatLab" project to preserve and harden — none existed.
Per the prompt's own Phase 0 rule, this was therefore executed as a **from-scratch
build** of the specified application. Nothing pre-existing was overwritten because
nothing pre-existing was present.

A complete, working, tested application was built:

- **Statistical modeling lab** (`statinvest/models/`)
  - OLS via stable QR/SVD least squares (no explicit matrix inverse); robust
    HC0/HC1/HC3 standard errors; VIF, Cook's distance, leverage, Breusch-Pagan;
    rank/condition/constant-column/tiny-sample detection.
  - Binary logistic regression via IRLS; numerically stable sigmoid & log-loss;
    ROC-AUC, PR-AUC, confusion matrix, precision/recall/F1, Brier score;
    separation, imbalance and non-convergence warnings.
  - Poisson regression via IRLS (log link); exposure/offset; deviance, Pearson
    residuals, overdispersion & excess-zero warnings; rejects non-integer counts.
  - Auditable transforms (level/log, standardization, interactions, polynomials);
    SGD/Adam optimization lab with finite-difference gradient checks and
    reference-estimator comparison; leakage-resistant chronological/walk-forward
    splits; JSON (never pickle) run serialization with a secret-key guard.
- **Versioned SQLite persistence** (`statinvest/database/`) — ordered migrations,
  `foreign_keys=ON` + WAL, parameterized idempotent CRUD, verified timestamped
  backups before migration, integrity checks.
- **Generalized multi-asset market layer** (`statinvest/market/`) — symbol
  validation (never shell-interpolated), agorot→ILS normalization with a retained
  audit rule, an offline deterministic **synthetic provider**, and an optional
  yfinance provider with timeouts + bounded retries.
- **Shared service layer + two UIs + unified launcher** — `AnalysisService` is
  the single persistence path; Streamlit (localhost) and Tkinter desktop both
  call it; `main.py` exposes `smoke / integrity / backup / streamlit / desktop`.
- **Tests & docs** — 68 offline deterministic tests + smoke test; README,
  ARCHITECTURE, SECURITY, PyInstaller spec.

## Verification (this run)

- `pytest`: **68 passed, 1 deselected** (network test).
- `python smoke_test.py`: **SMOKE PASS ✅**.
- `python -m compileall`: OK.
- Database integrity: schema v2, `integrity ok`, 0 FK violations.

See `TEST_RESULTS.md` for full captured output.

## How to retrieve

This build was produced in a remote cloud workspace. Files live at the workspace
path recorded in this folder — see `RUN_INSTRUCTIONS.md`. The private-Git push is
the second recovery channel. Nothing was transferred to your phone/computer
automatically; use the ZIP in this folder or the Git branch.
