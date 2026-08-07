# ARCHITECTURE SUMMARY

Shared-layer design; both UIs call the same `AnalysisService`.

```
main.py -> statinvest.launcher (argparse: smoke/integrity/backup/streamlit/desktop)
  AnalysisService (statinvest/service.py)  <- single persistence path
    ├── statinvest.market   provider (synthetic offline + optional yfinance),
    │                       validate (no shell interpolation), normalize (agorot->ILS, audited)
    ├── statinvest.database  schema (ordered migrations), db (FK on, WAL, backup, integrity),
    │                        repository (parameterized, idempotent upserts)
    └── statinvest.models    linear (QR/SVD OLS), logistic (IRLS), poisson (IRLS),
                             transforms, optim (SGD/Adam + grad-check), evaluation, serialize
  UIs: statinvest.ui.streamlit_app (localhost), statinvest.ui.desktop (Tkinter)
```

## Database schema (v2)

- `assets(symbol UNIQUE, display_name, exchange, quote_currency, asset_type, country, provider, first/last_seen_utc, metadata_json)`
- `market_snapshots(... UNIQUE(asset_id, fetched_at_utc, source), normalization_rule)`
- `price_history(... UNIQUE(asset_id, interval, ts_utc))`
- `watchlists(name UNIQUE)`, `watchlist_items(UNIQUE(watchlist_id, asset_id))`
- `schema_migrations(version PK, description, applied_at_utc)`
- Indexes: `assets(symbol)`, `market_snapshots(asset_id, fetched_at_utc)`, `price_history(asset_id, interval, ts_utc)`

## Database path strategy

Per-user application-data directory
(`~/.local/share/statistics-investment-eco-system/`), overridable with
`STATINVEST_DATA_DIR`; `:memory:` supported for tests. Not committed to Git.

## Data provenance labels

`LIVE` / `DELAYED` / `CACHED` / `SYNTHETIC` / `PARTIAL` / `ERROR`.
