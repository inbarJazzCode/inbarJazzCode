# Architecture

The application is organized into clear shared layers so both the desktop and
Streamlit UIs call the *same* tested service functions — persistence is never
duplicated in individual button handlers.

```
main.py
  └── statinvest.launcher            # argparse entry point (smoke/integrity/backup/streamlit/desktop)
        ├── statinvest.service       # AnalysisService — the single shared layer
        │     ├── statinvest.market  # provider + validation + normalization
        │     └── statinvest.database# SQLite schema, migrations, repository
        ├── statinvest.ui.streamlit_app
        └── statinvest.ui.desktop
statinvest.models                    # OLS / logistic / poisson / transforms / optim / evaluation
```

## Layers

- **`statinvest.market`** — `provider.py` (SyntheticProvider offline + optional
  YFinanceProvider with timeouts and bounded retries), `validate.py` (symbol
  validation, never shell-interpolated), `normalize.py` (auditable agorot→ILS
  rule with raw + normalized values retained).
- **`statinvest.database`** — `schema.py` (ordered migrations), `db.py`
  (connection management with `foreign_keys=ON` + WAL, migrations, verified
  backups, integrity checks), `repository.py` (parameterized, idempotent CRUD).
- **`statinvest.models`** — self-contained statistical estimators plus the
  optimization lab and leakage-resistant evaluation utilities.
- **`statinvest.service`** — combines the above; the only place that persists a
  fetched snapshot, so a logical action is saved exactly once.

## Database schema (version 2)

| Table | Purpose | Key uniqueness |
|-------|---------|----------------|
| `assets` | symbol metadata, provider, currency, type | `symbol` |
| `market_snapshots` | point-in-time quotes + fundamentals + provenance | `(asset_id, fetched_at_utc, source)` |
| `price_history` | OHLCV bars | `(asset_id, interval, ts_utc)` |
| `watchlists` / `watchlist_items` | research portfolios | `name`, `(watchlist_id, asset_id)` |
| `schema_migrations` | applied versions | `version` |

Indexes cover the common symbol/time access paths. All timestamps are UTC.
Upserts use `COALESCE` so a poorer later fetch never overwrites a good value.

## Persistence flow

1. UI calls `AnalysisService.fetch_symbol(symbol)`.
2. Symbol is validated; provider returns a `MarketData` with a status label.
3. On success the snapshot (and any history) is written through the repository
   with idempotent upserts.
4. A database failure is surfaced to the UI but does not crash the fetch — the
   `MarketData` is still returned.

## Reproducibility

Model runs serialize to JSON (`statinvest.models.serialize`) — never pickle —
capturing specification, features, transforms, seed, metrics, warnings and
provenance, so a run can be reconstructed while the underlying data is available.
