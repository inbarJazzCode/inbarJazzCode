"""Shared service layer used by BOTH the desktop and Streamlit UIs.

This is the single place that combines the provider, normalization and database
so persistence logic is not duplicated across button handlers. A database
failure is surfaced but does not crash a fetch when a safe read-only/synthetic
path exists.
"""

from __future__ import annotations

import csv
import io
from dataclasses import asdict

from statinvest.database.db import Database
from statinvest.database.repository import AssetRecord, Repository, SnapshotRecord
from statinvest.market.provider import MarketData, get_provider
from statinvest.market.validate import validate_symbol

# Minimum stored bars before a pair is worth modelling. Below this the
# standard errors are too wide for any conclusion to survive.
MIN_HISTORY_ROWS = 60


class AnalysisService:
    def __init__(self, db: Database | None = None, provider_name: str = "synthetic"):
        self.db = db or Database()
        self.migration_info = self.db.migrate()
        self.repo = Repository(self.db)
        self.provider_name = provider_name
        self.provider = get_provider(provider_name)

    # -- market fetch + persist ---------------------------------------------
    def fetch_symbol(self, symbol: str, persist: bool = True,
                     with_history: bool = False) -> dict:
        sym = validate_symbol(symbol)
        md = self.provider.fetch(sym, with_history=with_history)
        saved = False
        db_error = None
        if persist and md.data_status not in ("ERROR",):
            try:
                self._persist(md)
                saved = True
            except Exception as exc:  # visible but non-fatal
                db_error = f"{type(exc).__name__}: {exc}"
        return {
            "market_data": asdict(md),
            "persisted": saved,
            "db_error": db_error,
            "provider": self.provider_name,
        }

    def _persist(self, md: MarketData) -> None:
        asset = AssetRecord(
            symbol=md.symbol,
            display_name=md.display_name,
            exchange=md.exchange,
            quote_currency=md.normalized_currency,
            asset_type=md.asset_type,
            country=md.country,
            provider=md.source,
        )
        snap = SnapshotRecord(
            fetched_at_utc=md.fetched_at_utc,
            price=md.price,
            raw_price=md.raw_price,
            normalized_price=md.normalized_price,
            raw_currency=md.raw_currency,
            normalized_currency=md.normalized_currency,
            eps=md.eps,
            market_cap=md.market_cap,
            trailing_pe=md.trailing_pe,
            forward_pe=md.forward_pe,
            net_income=md.net_income,
            distance_from_high=md.distance_from_high,
            source=md.source,
            data_status=md.data_status,
            fetch_status=md.data_status,
            error_summary=md.error_summary,
            normalization_rule=md.normalization_rule,
        )
        self.repo.insert_snapshot(md.symbol, snap, asset=asset)
        if md.history:
            self.repo.insert_price_history(md.symbol, "1d", md.history, source=md.source)

    def scan(self, symbols: list[str], persist: bool = True) -> list[dict]:
        return [self.fetch_symbol(s, persist=persist) for s in symbols]

    # -- watchlists ----------------------------------------------------------
    def add_to_watchlist(self, name: str, symbol: str, notes: str | None = None) -> None:
        self.repo.add_to_watchlist(name, validate_symbol(symbol), notes)

    def watchlist_view(self, name: str) -> list[dict]:
        rows = self.repo.list_watchlist(name)
        out = []
        for r in rows:
            latest = self.repo.latest_snapshot(r["symbol"]) or {}
            out.append({
                "symbol": r["symbol"],
                "display_name": r.get("display_name"),
                "asset_type": r.get("asset_type"),
                "latest_price": latest.get("normalized_price"),
                "trailing_pe": latest.get("trailing_pe"),
                "fetched_at_utc": latest.get("fetched_at_utc"),
                "data_status": latest.get("data_status"),
                "notes": r.get("notes"),
            })
        return out

    # -- modelling on real stored securities ---------------------------------
    def stored_symbols(self, interval: str = "1d") -> list[str]:
        """Symbols that have enough stored history to model."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT a.symbol, COUNT(*) AS n
                FROM price_history h
                JOIN assets a ON a.id = h.asset_id
                WHERE h.interval = ?
                GROUP BY a.symbol
                HAVING n >= ?
                ORDER BY a.symbol
                """,
                (interval, MIN_HISTORY_ROWS),
            ).fetchall()
        return [r["symbol"] for r in rows]

    def returns_pair(self, target: str, predictor: str,
                     interval: str = "1d") -> dict:
        """Aligned daily simple returns for two stored securities.

        Returns are used rather than price levels: regressing one price series
        on another is a spurious regression, since both are non-stationary.
        Only dates present in *both* series are kept, so the pair is aligned on
        a shared calendar (relevant when the two trade on different exchanges).
        """
        target = validate_symbol(target)
        predictor = validate_symbol(predictor)
        if target == predictor:
            raise ValueError(
                "Target and predictor must be different securities; regressing "
                "a series on itself is not a meaningful model."
            )

        def closes(sym: str) -> dict:
            rows = self.repo.get_price_history(sym, interval)
            out = {}
            for r in rows:
                price = r.get("adj_close")
                if price is None:
                    price = r.get("close")
                if price is not None:
                    out[r["ts_utc"][:10]] = float(price)
            return out

        a, b = closes(target), closes(predictor)
        for sym, series in ((target, a), (predictor, b)):
            if len(series) < MIN_HISTORY_ROWS:
                raise ValueError(
                    f"Not enough stored history for {sym} "
                    f"({len(series)} rows, need {MIN_HISTORY_ROWS}). "
                    "Fetch it on the Market data tab first."
                )

        dates = sorted(set(a) & set(b))
        if len(dates) < MIN_HISTORY_ROWS:
            raise ValueError(
                f"{target} and {predictor} only overlap on {len(dates)} dates "
                f"(need {MIN_HISTORY_ROWS}). Their trading calendars may differ."
            )

        y, x, when = [], [], []
        for i in range(1, len(dates)):
            prev, cur = dates[i - 1], dates[i]
            y.append((a[cur] - a[prev]) / a[prev])
            x.append((b[cur] - b[prev]) / b[prev])
            when.append(cur)
        return {"target": target, "predictor": predictor,
                "y": y, "x": x, "dates": when, "n": len(y)}

    def fit_market_model(self, target: str, predictor: str,
                         interval: str = "1d", se_type: str = "hc3",
                         train_frac: float = 0.70) -> dict:
        """Fit OLS and a logistic direction model on two real securities.

        Runs the full honest analysis in one call: the market model with robust
        standard errors, a heteroskedasticity test, a chronologically split
        logistic classifier, and the majority-class baseline it must beat.
        Nothing here is shuffled -- every training date precedes every test date.
        """
        import numpy as np

        from statinvest.models.evaluation import chronological_split
        from statinvest.models.linear import OLSModel
        from statinvest.models.logistic import LogisticModel

        pair = self.returns_pair(target, predictor, interval)
        y = np.asarray(pair["y"], dtype=float)
        x = np.asarray(pair["x"], dtype=float)
        dates = pair["dates"]

        ols = OLSModel()
        res = ols.fit(x.reshape(-1, 1), y,
                      feature_names=[f"r_{predictor}"], se_type=se_type)
        classical = OLSModel().fit(x.reshape(-1, 1), y,
                                   feature_names=[f"r_{predictor}"],
                                   se_type="classical")
        bp = ols.breusch_pagan()

        robust_se = res.coefficient_table()[1]["std_err"]
        naive_se = classical.coefficient_table()[1]["std_err"]
        se_inflation = (robust_se / naive_se - 1) * 100 if naive_se else float("nan")

        # Direction model, validated on dates the fit never saw.
        binary = (y > 0).astype(int)
        feature = x.reshape(-1, 1) * 100  # percent, so the odds ratio reads per 1%
        split = chronological_split(len(y), train_frac, 0.0)
        tr, te = split.train_idx, split.test_idx

        full = LogisticModel()
        full_res = full.fit(feature, binary, feature_names=["mkt"])
        split_model = LogisticModel()
        split_model.fit(feature[tr], binary[tr], feature_names=["mkt"])
        in_sample = split_model.classification_metrics(feature[tr], binary[tr])
        out_sample = split_model.classification_metrics(feature[te], binary[te])
        up_rate = float(binary[te].mean())
        baseline = max(up_rate, 1 - up_rate)

        return {
            "pair": {"target": target, "predictor": predictor, "n": pair["n"],
                     "from": dates[0], "to": dates[-1], "interval": interval},
            "ols": {
                "summary": res.summary(),
                "se_type": se_type,
                "se_inflation_pct": se_inflation,
                "breusch_pagan": bp,
                "heteroskedastic": bp["p_value"] < 0.05,
                "annualised_alpha_pct": float(res.params[0] * 252 * 100),
            },
            "logistic": {
                "converged": full_res.converged,
                "odds_ratio_per_1pct": float(
                    full_res.coefficient_table()[1]["odds_ratio"]),
                "p_value": float(full_res.coefficient_table()[1]["p_value"]),
                "mcfadden_r2": float(full_res.pseudo_r2_mcfadden),
                "in_sample": in_sample,
                "out_of_sample": out_sample,
                "baseline": baseline,
                "train_range": [dates[tr[0]], dates[tr[-1]]],
                "test_range": [dates[te[0]], dates[te[-1]]],
                "generalises": out_sample["roc_auc"] >= 0.60,
                "beats_baseline": out_sample["accuracy"] > baseline,
            },
        }

    # -- status --------------------------------------------------------------
    def status(self) -> dict:
        integ = self.db.integrity_check()
        return {
            "db_path": "(configured application-data directory)",
            "schema_version": integ["schema_version"],
            "integrity_ok": integ["ok"],
            "row_counts": integ["row_counts"],
            "provider": self.provider_name,
            "migration": self.migration_info,
        }


# -- CSV export with formula-injection protection ---------------------------
_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_cell(value) -> str:
    """Neutralize spreadsheet formula injection.

    A leading =, +, -, @, tab or CR can trigger formula execution in Excel /
    Sheets. We prefix such cells with a single quote so they are treated as text.
    """
    if value is None:
        return ""
    s = str(value)
    if s and s[0] in _DANGEROUS_PREFIXES:
        return "'" + s
    return s


def export_watchlist_csv(rows: list[dict]) -> str:
    """Return a UTF-8 CSV string with sanitized cells and no internal paths."""
    fields = ["symbol", "display_name", "asset_type", "latest_price",
              "trailing_pe", "fetched_at_utc", "data_status", "notes"]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(fields)
    for r in rows:
        writer.writerow([sanitize_cell(r.get(f)) for f in fields])
    return buf.getvalue()
