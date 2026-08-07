"""High-level, parameterized data access for the application.

All SQL is parameterized. Inserts are idempotent through unique constraints and
``ON CONFLICT`` upsert logic, so re-saving the same snapshot or history row does
not create duplicates and does not silently overwrite a good value with a poorer
one.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from statinvest.database.db import Database, utc_now_iso


@dataclass
class AssetRecord:
    symbol: str
    display_name: str | None = None
    exchange: str | None = None
    quote_currency: str | None = None
    asset_type: str | None = None
    country: str | None = None
    provider: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SnapshotRecord:
    fetched_at_utc: str
    price: float | None = None
    raw_price: float | None = None
    normalized_price: float | None = None
    raw_currency: str | None = None
    normalized_currency: str | None = None
    eps: float | None = None
    market_cap: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    net_income: float | None = None
    distance_from_high: float | None = None
    source: str | None = None
    data_status: str | None = None
    fetch_status: str | None = None
    error_summary: str | None = None
    normalization_rule: str | None = None


class Repository:
    def __init__(self, db: Database):
        self.db = db

    # -- assets --------------------------------------------------------------
    def upsert_asset(self, asset: AssetRecord) -> int:
        now = utc_now_iso()
        meta = json.dumps(asset.metadata) if asset.metadata else None
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO assets(symbol, display_name, exchange, quote_currency,
                    asset_type, country, provider, first_seen_utc, last_seen_utc,
                    metadata_json)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(symbol) DO UPDATE SET
                    display_name = COALESCE(excluded.display_name, assets.display_name),
                    exchange = COALESCE(excluded.exchange, assets.exchange),
                    quote_currency = COALESCE(excluded.quote_currency, assets.quote_currency),
                    asset_type = COALESCE(excluded.asset_type, assets.asset_type),
                    country = COALESCE(excluded.country, assets.country),
                    provider = COALESCE(excluded.provider, assets.provider),
                    last_seen_utc = excluded.last_seen_utc,
                    metadata_json = COALESCE(excluded.metadata_json, assets.metadata_json)
                """,
                (asset.symbol, asset.display_name, asset.exchange, asset.quote_currency,
                 asset.asset_type, asset.country, asset.provider, now, now, meta),
            )
            row = conn.execute(
                "SELECT id FROM assets WHERE symbol = ?", (asset.symbol,)
            ).fetchone()
            return int(row["id"])

    def get_asset(self, symbol: str) -> dict | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM assets WHERE symbol = ?", (symbol,)).fetchone()
            return dict(row) if row else None

    # -- snapshots -----------------------------------------------------------
    def insert_snapshot(self, symbol: str, snap: SnapshotRecord,
                        asset: AssetRecord | None = None) -> int:
        asset = asset or AssetRecord(symbol=symbol)
        asset_id = self.upsert_asset(asset)
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO market_snapshots(asset_id, fetched_at_utc, price, raw_price,
                    normalized_price, raw_currency, normalized_currency, eps, market_cap,
                    trailing_pe, forward_pe, net_income, distance_from_high, source,
                    data_status, fetch_status, error_summary, normalization_rule)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(asset_id, fetched_at_utc, source) DO NOTHING
                """,
                (asset_id, snap.fetched_at_utc, snap.price, snap.raw_price,
                 snap.normalized_price, snap.raw_currency, snap.normalized_currency,
                 snap.eps, snap.market_cap, snap.trailing_pe, snap.forward_pe,
                 snap.net_income, snap.distance_from_high, snap.source, snap.data_status,
                 snap.fetch_status, snap.error_summary, snap.normalization_rule),
            )
            if cur.lastrowid:
                return int(cur.lastrowid)
            row = conn.execute(
                "SELECT id FROM market_snapshots WHERE asset_id=? AND fetched_at_utc=? "
                "AND source IS ?",
                (asset_id, snap.fetched_at_utc, snap.source),
            ).fetchone()
            return int(row["id"]) if row else -1

    def latest_snapshot(self, symbol: str) -> dict | None:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT s.* FROM market_snapshots s
                JOIN assets a ON a.id = s.asset_id
                WHERE a.symbol = ?
                ORDER BY s.fetched_at_utc DESC LIMIT 1
                """,
                (symbol,),
            ).fetchone()
            return dict(row) if row else None

    def count_snapshots(self, symbol: str) -> int:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM market_snapshots s "
                "JOIN assets a ON a.id = s.asset_id WHERE a.symbol = ?",
                (symbol,),
            ).fetchone()
            return int(row["c"])

    # -- price history -------------------------------------------------------
    def insert_price_history(self, symbol: str, interval: str,
                            rows: list[dict], source: str | None = None) -> int:
        asset_id = self.upsert_asset(AssetRecord(symbol=symbol))
        inserted = 0
        with self.db.connect() as conn:
            for r in rows:
                cur = conn.execute(
                    """
                    INSERT INTO price_history(asset_id, interval, ts_utc, open, high,
                        low, close, adj_close, volume, source)
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(asset_id, interval, ts_utc) DO NOTHING
                    """,
                    (asset_id, interval, r["ts_utc"], r.get("open"), r.get("high"),
                     r.get("low"), r.get("close"), r.get("adj_close"), r.get("volume"),
                     source),
                )
                if cur.lastrowid:
                    inserted += 1
        return inserted

    def get_price_history(self, symbol: str, interval: str) -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT h.* FROM price_history h
                JOIN assets a ON a.id = h.asset_id
                WHERE a.symbol = ? AND h.interval = ?
                ORDER BY h.ts_utc ASC
                """,
                (symbol, interval),
            ).fetchall()
            return [dict(r) for r in rows]

    # -- watchlists ----------------------------------------------------------
    def create_watchlist(self, name: str) -> int:
        now = utc_now_iso()
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO watchlists(name, created_utc, updated_utc) VALUES(?,?,?) "
                "ON CONFLICT(name) DO NOTHING",
                (name, now, now),
            )
            row = conn.execute("SELECT id FROM watchlists WHERE name = ?", (name,)).fetchone()
            return int(row["id"])

    def add_to_watchlist(self, name: str, symbol: str, notes: str | None = None) -> None:
        wl_id = self.create_watchlist(name)
        asset_id = self.upsert_asset(AssetRecord(symbol=symbol))
        now = utc_now_iso()
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO watchlist_items(watchlist_id, asset_id, notes, added_utc) "
                "VALUES(?,?,?,?) ON CONFLICT(watchlist_id, asset_id) DO UPDATE SET "
                "notes = COALESCE(excluded.notes, watchlist_items.notes)",
                (wl_id, asset_id, notes, now),
            )
            conn.execute("UPDATE watchlists SET updated_utc = ? WHERE id = ?", (now, wl_id))

    def remove_from_watchlist(self, name: str, symbol: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                DELETE FROM watchlist_items
                WHERE watchlist_id = (SELECT id FROM watchlists WHERE name = ?)
                  AND asset_id = (SELECT id FROM assets WHERE symbol = ?)
                """,
                (name, symbol),
            )

    def list_watchlist(self, name: str) -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT a.symbol, a.display_name, a.asset_type, i.notes, i.added_utc
                FROM watchlist_items i
                JOIN watchlists w ON w.id = i.watchlist_id
                JOIN assets a ON a.id = i.asset_id
                WHERE w.name = ?
                ORDER BY a.symbol
                """,
                (name,),
            ).fetchall()
            return [dict(r) for r in rows]
