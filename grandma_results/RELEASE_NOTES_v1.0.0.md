# Invest-System v1.0.0 — Release Notes

**Eco-Platform · OLS · Logistic · Poisson — by Inbar**
Released 8 August 2026

---

## Run it in three steps

1. **Unzip** this folder anywhere (Desktop is fine).
2. **Double-click `CREATE_DESKTOP_ICON`** — once. You get an *Invest-System - Inbar*
   icon on your Desktop.
3. **Double-click that icon.** First run takes 2–3 minutes while it installs; after
   that it opens in seconds.

Requires **Python 3.11+** ([python.org/downloads](https://www.python.org/downloads/)).
On Windows, tick **"Add Python to PATH"** on the installer's first screen — skipping
that box causes most first-run failures.

Prefer the terminal? `python main.py streamlit`. Other modes: `smoke`, `integrity`,
`backup`, `desktop`.

---

## What it does

A statistical laboratory that reads market data — not a trading terminal. It is
built to stop you believing a model that only looks convincing.

### Five screens

| Screen | What it does |
|---|---|
| **Market data** | Fetch any Yahoo-resolvable symbol. Live price, trailing and forward P/E, market cap, with a provenance badge and a full normalization audit trail. |
| **Model lab** | Fit OLS, logistic or Poisson — on **securities you fetched**, or on synthetic data with known coefficients to verify the estimator. |
| **Estimator comparison** | Closed form / IRLS vs SGD vs Adam on the same objective, with loss curves and explicit convergence verdicts. |
| **AI explainer** | Optional plain-language explanation via any OpenAI-compatible backend, including free local models. |
| **Watchlist** | Persisted research list with formula-injection-safe CSV export. |

### The statistics

- **OLS** — QR/SVD least squares (never an explicit matrix inverse). Classical and
  HC0/HC1/HC3 robust standard errors, VIF, Cook's distance, leverage,
  Breusch-Pagan, rank and conditioning checks.
- **Logistic** — IRLS on the binomial log-loss, numerically stable sigmoid,
  ROC-AUC and PR-AUC, confusion matrix, Brier score. Warns on separation,
  class imbalance and non-convergence.
- **Poisson** — log link, exposure/offset support, deviance and Pearson residuals,
  overdispersion and excess-zero diagnostics. Refuses to treat continuous returns
  as counts.
- **Evaluation** — chronological splits and expanding-window walk-forward. Never
  shuffled, so no future data leaks into a fit.
- **Optimisation lab** — SGD and Adam with finite-difference gradient checks,
  always compared against a trusted reference estimator.

---

## What makes it different

Every number ships with its caveat attached:

- A beta always carries its **robust** standard error. On real data the robust
  error ran **46% larger** than the classical one — the usual default would have
  overstated precision by nearly half.
- A classifier score always carries its **out-of-sample** counterpart *and* the
  majority-class baseline it must beat.
- A fit that did not converge is **labelled**, never silently rendered as a result.
- A missing P/E is **explained** ("this is an index, it has no earnings") rather
  than left blank.
- Demo data is labelled `SYNTHETIC` so it can never be mistaken for market data.

---

## Verified in this release

| Check | Result |
|---|---|
| Test suite | **92 passed** (1 network test deselected) |
| End-to-end smoke | **SMOKE PASS** |
| Byte-compile | OK |
| Database integrity | schema v2, `ok`, 0 FK violations |
| Live data fetch | Working (Yahoo chart API + cookie/crumb for fundamentals) |
| Source language | English only, enforced by a test |
| Secrets in repo | None tracked |

The in-app result for KO reproduces the standalone analysis exactly —
β = 0.2634, R² = 0.0728, robust SE +46%, AUC 0.685 → 0.438.

---

## Privacy

Local-first. The database lives in your own user folder
(`~/.local/share/invest-system/`). No telemetry, no analytics, no accounts.
Streamlit's usage reporting is switched off. The only outbound calls are market-data
fetches you trigger, plus the AI explainer **if** you enable it — and that ships
with a panel showing the exact JSON before anything is sent.

Any API key is read from an environment variable only. It is never written to the
database, committed, logged or displayed.

---

## Known limits

- Accessibility has not been formally audited.
- Layout is desktop-first; narrow windows reflow via framework defaults.
- Results are tabular — residual and leverage plots are not drawn yet.
- Live data depends entirely on Yahoo coverage and rate limits.

---

**Educational and research use only.** Market data may be delayed. This is **not
investment advice**. No brokerage integration, order placement or automated trading
is provided — by design. No transaction costs, spreads or slippage are modelled
anywhere, so nothing here is a trading strategy.
