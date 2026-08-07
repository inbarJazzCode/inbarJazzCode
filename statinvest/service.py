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
