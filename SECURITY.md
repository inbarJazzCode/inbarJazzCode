# Security & Data Protection

This document records the focused security review and the protections in place.

## Threats reviewed

| Area | Status | Mitigation |
|------|--------|------------|
| SQL injection | Mitigated | 100% parameterized SQL; no string/f-string SQL from user input. Table names in maintenance queries are fixed literals only. |
| Command injection | Mitigated | Ticker symbols are validated (`statinvest.market.validate`) and never passed to a shell. The only `subprocess` call launches Streamlit with a fixed argument vector (no `shell=True`). |
| Unsafe deserialization | Mitigated | Model persistence is JSON only — no `pickle`/`eval`/`exec`. A secret-key scan refuses to serialize credential-like fields. |
| Path traversal (import/export) | Mitigated | Symbols reject path-like input; exports return in-memory CSV strings and never embed internal filesystem paths. |
| CSV formula injection | Mitigated | `sanitize_cell` prefixes `= + - @ TAB CR` leading cells with `'`. |
| Secret leakage | Mitigated | `.gitignore` excludes `.env`, keys, databases, backups, exports, logs. No secrets are logged or committed. Error summaries stored in the DB are non-sensitive type names. |
| Public server binding | Mitigated | Streamlit is launched with `--server.address localhost`. No other listeners. |
| Unbounded network retries / DoS | Mitigated | The yfinance provider uses fixed retries with backoff and timeouts; it never loops indefinitely. |
| Giant CSV / DoS on import | N/A (by design) | The app does not import arbitrary user CSVs into the model path in this version; exports are bounded to watchlist rows. |
| Database corruption under concurrency | Mitigated | `foreign_keys=ON`, WAL journal, `busy_timeout`, transactions with rollback, verified backups before migration. |

## Data protection guarantees

- The user's live database is never deleted, reset or silently replaced.
- A timestamped backup is created **and re-opened/verified** before any schema
  migration advances the version.
- The live database, caches, exports and logs are Git-ignored; only schema,
  migrations, code, tests and a tiny synthetic fixture are tracked.
- No telemetry, analytics, remote logging or hidden uploads.
- No brokerage integration, order placement, automated trading or credential
  storage.

## Dependency audit

`pip-audit` was run. No vulnerabilities were found in the application's direct
dependencies (numpy, scipy, pandas, streamlit, yfinance). Advisories reported by
the tool pertain to pre-existing **base-environment system packages** (pip,
setuptools, wheel, urllib3, pyjwt) that this project does not introduce; breaking
upgrades to base tooling are intentionally not auto-applied.

## Reporting

This is an educational project. Report issues via the private repository's issue
tracker. Do not include secrets or personal holdings in reports.
