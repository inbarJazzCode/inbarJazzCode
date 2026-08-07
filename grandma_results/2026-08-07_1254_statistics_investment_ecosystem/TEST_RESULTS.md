# TEST RESULTS — 2026-08-07_1254

Captured from a clean working state in this run.

```
### pytest (offline)
....................................................................     [100%]
68 passed, 1 deselected in 1.71s

### smoke_test.py
[PASS] OLS coefficient recovery
[PASS] Logistic converged
[PASS] Logistic ROC-AUC > 0.7
[PASS] Poisson converged
[PASS] Adam matches least-squares reference
[PASS] DB migrated to latest schema
[PASS] DB integrity ok
[PASS] Snapshot persisted
[PASS] Idempotent snapshot (no duplicate)
[PASS] Watchlist has one item
[PASS] CSV formula injection sanitized
[PASS] Chronological split leakage-free
[PASS] Agorot normalized to ILS
----------------------------------------
SMOKE PASS ✅

### compileall
compileall OK

### database integrity (fresh db)
Schema version : 2
Integrity      : ok
FK violations  : 0
Row counts     : {'assets': 0, 'market_snapshots': 0, 'price_history': 0, 'watchlists': 0, 'watchlist_items': 0}
```

## Coverage of required test cases
- database initialization, migration, backup-before-migration — test_database.py
- snapshot insertion + idempotent duplicate — test_database.py
- historical-price deduplication — test_database.py
- multi-asset metadata with missing fields — test_database.py / test_market_and_service.py
- watchlist create/add/remove/read — test_database.py
- UTC timestamps — test_database.py
- currency/unit normalization + P/E consistency — test_market_and_service.py
- database integrity check — test_database.py
- CSV export sanitization — test_market_and_service.py
- synthetic/offline fallback — test_market_and_service.py
- unified launcher argument parsing — test_launcher.py
- OLS coefficient recovery / singular design / robust SE — test_models_ols.py
- logistic separation & imbalance — test_models_logistic.py
- Poisson zero counts / offsets / overdispersion — test_models_poisson.py
- invalid logarithms — test_models_support.py
- optimizer reproducibility / non-convergence / gradient check — test_models_support.py
- leakage-resistant chronological splitting — test_models_support.py
- serialization of configuration and results without secrets — test_models_support.py
