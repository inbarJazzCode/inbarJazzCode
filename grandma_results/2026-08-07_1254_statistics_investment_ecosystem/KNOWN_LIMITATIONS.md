# KNOWN LIMITATIONS

## Scope / reality
- The repository started **empty**, so this is a from-scratch build, not a
  migration of prior "TA125 StatLab" code. There was no legacy `app.py`,
  Streamlit app, `database.py` or React prototype to preserve.

## Market data
- Live data availability depends entirely on **Yahoo/yfinance coverage** and its
  rate limits. The yfinance provider was not exercised against the live network
  in this run (the offline synthetic provider is the default and powers all
  deterministic tests). Run `pytest -m network` to exercise it live.
- The synthetic provider produces deterministic, clearly-labelled `SYNTHETIC`
  data for offline use — it is not real market data.
- Agorot→ILS normalization triggers only when the provider reports `ILA`/agorot
  currency; symbols are not divided by 100 based on suffix guessing.

## Statistical
- Logistic/Poisson inference assumes IRLS convergence; non-convergence and
  separation are warned but not auto-corrected (no penalized-likelihood Firth
  fallback in this version).
- Poisson overdispersion is diagnosed but a negative-binomial/quasi-Poisson
  estimator is not yet implemented.
- Walk-forward evaluation provides splitting utilities and a naive baseline;
  it does not include a full automated backtesting/portfolio engine (by design —
  no trade execution).

## Packaging / UI
- The PyInstaller build was **not executed** in this Linux cloud environment
  (Tkinter is unavailable headless and the desktop binary targets Windows). The
  spec is provided and the launcher is import-tested. Verify the packaged binary
  on a Windows machine.
- The desktop UI requires a display; it degrades to a clear message when headless.

## Environment
- `pip-audit` advisories affect pre-existing base-image system packages (pip,
  setuptools, wheel, urllib3, pyjwt), not the app's direct dependencies. Breaking
  base upgrades are intentionally not auto-applied.
