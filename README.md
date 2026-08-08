# Invest-System — OLS, Logistic & Poisson

A **local-first, research-grade** investment-analysis application. It combines a
transparent statistical-modeling laboratory (OLS, binary logistic and Poisson
regression, plus an SGD/Adam optimization lab) with a reliable SQLite
persistence layer and a generalized multi-asset market-data service.

> **Educational / research use only.** Market data may be delayed and depends on
> third-party (Yahoo/yfinance) coverage. **This is not investment advice.** There
> is no brokerage integration, order placement or automated trading.

---

## What this is (and is not)

- It **is** an auditable statistics lab for investment research: fit models, read
  diagnostics, compare optimizers against trusted reference estimators, and store
  reproducible runs.
- It is **not** a trading system, a signal service, or a claim that a low P/E
  means "buy". Research language is deliberately neutral.

## Asset coverage

The app accepts any symbol the configured provider (Yahoo/yfinance) can resolve —
equities, indices (`^GSPC`), ETFs (`SPY`), currencies (`EURUSD=X`) and crypto
(`BTC-USD`). **Availability depends on Yahoo/yfinance coverage**; missing fields
(EPS, P/E, market cap) are normal for asset classes where they don't apply.

**TA-125 is preserved as a preset and educational example, not the whole scope.**
A fully offline **synthetic provider** powers tests and works with no network.

## Install

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt                        # add -r requirements-dev.txt for tests
```

## Run

```bash
python main.py smoke          # offline end-to-end smoke test -> "SMOKE PASS ✅"
python main.py streamlit      # Streamlit UI, bound to localhost
python main.py desktop        # Tkinter desktop UI (falls back gracefully if headless)
python main.py integrity      # database integrity check
python main.py backup         # create + verify a timestamped DB backup
```

On Windows, `run_windows.bat [mode]` wraps the same launcher.

## Statistical modeling

| Family   | Estimator                    | Highlights |
|----------|------------------------------|------------|
| OLS      | QR/SVD least squares (no explicit inverse) | robust HC0/HC1/HC3 SEs, VIF, Cook's distance, Breusch-Pagan, condition number, rank checks |
| Logistic | IRLS (Newton)                | stable sigmoid & log-loss, ROC-AUC / PR-AUC, separation & imbalance warnings |
| Poisson  | IRLS, log link               | offset/exposure, deviance, Pearson residuals, overdispersion & excess-zero warnings |

### Modelling real securities

Fetch two symbols on the **Market data** tab, then open the **Model lab** and pick
them from the dropdowns. The app fits the market model on their actual aligned daily
returns, with HC3 robust standard errors, a heteroskedasticity test, and a
chronologically split direction model tested on dates the fit never saw. Whether the
relationship generalises is stated plainly, alongside the majority-class baseline it
has to beat.

Supporting tools: auditable level/log transformations, an SGD/Adam optimization
lab with finite-difference gradient checks and reference-estimator comparison,
and leakage-resistant chronological / walk-forward splitting.

## Data storage

SQLite lives in a per-user application-data directory
(`~/.local/share/invest-system/statinvest.db`, overridable via
`STATINVEST_DATA_DIR`). Schema is versioned with ordered migrations; a verified
timestamped backup is taken before any schema upgrade. See
[`ARCHITECTURE.md`](ARCHITECTURE.md).

### Backup & restore

```bash
python main.py backup                              # writes backups/statinvest.<UTC>.bak
# Restore: stop the app, copy the chosen .bak over statinvest.db.
```

Data provenance is labelled everywhere: **LIVE / DELAYED / CACHED / SYNTHETIC /
PARTIAL / ERROR**.

## Tests

```bash
pytest              # offline suite (network tests deselected by default)
pytest -m network   # optional live-Yahoo integration test
```

## Privacy & security

No telemetry, analytics or hidden uploads. Local web services bind to localhost.
CSV export sanitizes formula-injection and never emits internal paths. See
[`SECURITY.md`](SECURITY.md).
