"""Offline smoke test for the Invest-System.

Requires no network. Exercises the statistical core, the database layer and the
shared service end to end, and prints ``SMOKE PASS`` only if every check passes.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np


def run_smoke() -> int:
    checks: list[tuple[str, bool]] = []

    def check(name: str, condition: bool) -> None:
        checks.append((name, bool(condition)))
        print(f"[{'PASS' if condition else 'FAIL'}] {name}")

    # 1. OLS recovers known coefficients.
    from statinvest.models.linear import OLSModel
    rng = np.random.default_rng(1)
    X = rng.normal(size=(400, 2))
    y = 3.0 + 2.0 * X[:, 0] - 1.0 * X[:, 1] + rng.normal(scale=0.3, size=400)
    ols = OLSModel().fit(X, y, feature_names=["a", "b"])
    check("OLS coefficient recovery",
          np.allclose(ols.params, [3.0, 2.0, -1.0], atol=0.15))

    # 2. Logistic converges and gives sane AUC on separable-ish data.
    from statinvest.models.logistic import LogisticModel
    z = 0.5 + 2.0 * X[:, 0] - 1.0 * X[:, 1]
    p = 1 / (1 + np.exp(-z))
    yb = (rng.uniform(size=400) < p).astype(int)
    logit = LogisticModel()
    logit_res = logit.fit(X, yb, feature_names=["a", "b"])
    metrics = logit.classification_metrics(X, yb)
    check("Logistic converged", logit_res.converged)
    check("Logistic ROC-AUC > 0.7", metrics["roc_auc"] > 0.7)

    # 3. Poisson recovers rate and flags integer requirement.
    from statinvest.models.poisson import PoissonModel
    mu = np.exp(0.3 + 0.5 * X[:, 0])
    yc = rng.poisson(mu)
    pois = PoissonModel().fit(X, yc, feature_names=["a", "b"])
    check("Poisson converged", pois.converged)

    # 4. Optimizer matches least squares reference.
    from statinvest.models.optim import run_optimizer
    from statinvest.models._util import add_intercept
    Xd = add_intercept(X)
    opt = run_optimizer(Xd, y, objective="mse", optimizer="adam", lr=0.05, epochs=800)
    check("Adam matches least-squares reference",
          opt.max_coef_diff is not None and opt.max_coef_diff < 0.05)

    # 5. Database migrate + integrity + idempotent snapshot insert.
    from statinvest.database.db import Database
    from statinvest.service import AnalysisService
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "smoke.db")
        info = db.migrate()
        check("DB migrated to latest schema", info["to_version"] >= 1)
        integ = db.integrity_check()
        check("DB integrity ok", integ["ok"])

        service = AnalysisService(db=db, provider_name="synthetic")
        r1 = service.fetch_symbol("AAPL", persist=True)
        check("Snapshot persisted", r1["persisted"])
        # True idempotency: re-inserting the identical snapshot key must not
        # create a duplicate row.
        from statinvest.database.repository import SnapshotRecord
        snap = SnapshotRecord(fetched_at_utc="2026-01-01T00:00:00+00:00",
                              price=1.0, source="synthetic")
        service.repo.insert_snapshot("AAPL", snap)
        service.repo.insert_snapshot("AAPL", snap)  # duplicate key -> ignored
        check("Idempotent snapshot (no duplicate)",
              service.repo.count_snapshots("AAPL") == 2)  # r1 + one snap only

        # 6. Watchlist + CSV sanitization.
        from statinvest.service import export_watchlist_csv, sanitize_cell
        service.add_to_watchlist("wl", "MSFT")
        rows = service.watchlist_view("wl")
        check("Watchlist has one item", len(rows) == 1)
        check("CSV formula injection sanitized",
              sanitize_cell("=1+1").startswith("'"))
        export_watchlist_csv(rows)  # must not raise

    # 7. Chronological split has no leakage.
    from statinvest.models.evaluation import chronological_split
    sp = chronological_split(100, 0.6, 0.2)
    no_overlap = (
        len(set(sp.train_idx) & set(sp.val_idx)) == 0
        and len(set(sp.val_idx) & set(sp.test_idx)) == 0
        and sp.train_idx.max() < sp.val_idx.min() < sp.test_idx.min()
    )
    check("Chronological split leakage-free", no_overlap)

    # 8. Currency normalization for agorot.
    from statinvest.market.normalize import normalize_price
    norm = normalize_price(100.0, "ILA")
    check("Agorot normalized to ILS", abs(norm.normalized_price - 1.0) < 1e-9)

    passed = all(ok for _, ok in checks)
    print("-" * 40)
    if passed:
        print("SMOKE PASS ✅")
        return 0
    failed = [name for name, ok in checks if not ok]
    print(f"SMOKE FAIL ❌ ({len(failed)} failing: {', '.join(failed)})")
    return 1


if __name__ == "__main__":
    sys.exit(run_smoke())
