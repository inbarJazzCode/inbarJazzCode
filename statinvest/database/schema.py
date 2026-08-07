"""Schema definitions and ordered migrations.

Each migration is a ``(version, description, sql)`` tuple applied in order. The
``schema_migrations`` table records which versions have run. All statements use
fixed DDL — never string-built from user input.
"""

from __future__ import annotations

MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "initial schema: assets, market_snapshots, price_history, watchlists",
        """
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL UNIQUE,
            display_name TEXT,
            exchange TEXT,
            quote_currency TEXT,
            asset_type TEXT,
            country TEXT,
            provider TEXT,
            first_seen_utc TEXT NOT NULL,
            last_seen_utc TEXT NOT NULL,
            metadata_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_assets_symbol ON assets(symbol);

        CREATE TABLE IF NOT EXISTS market_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
            fetched_at_utc TEXT NOT NULL,
            price REAL,
            raw_price REAL,
            normalized_price REAL,
            raw_currency TEXT,
            normalized_currency TEXT,
            eps REAL,
            market_cap REAL,
            trailing_pe REAL,
            forward_pe REAL,
            net_income REAL,
            distance_from_high REAL,
            source TEXT,
            data_status TEXT,          -- LIVE | CACHED | DELAYED | SYNTHETIC | ERROR | PARTIAL
            fetch_status TEXT,
            error_summary TEXT,
            UNIQUE(asset_id, fetched_at_utc, source)
        );
        CREATE INDEX IF NOT EXISTS idx_snap_asset_time
            ON market_snapshots(asset_id, fetched_at_utc);

        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
            interval TEXT NOT NULL,
            ts_utc TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            adj_close REAL,
            volume REAL,
            source TEXT,
            UNIQUE(asset_id, interval, ts_utc)
        );
        CREATE INDEX IF NOT EXISTS idx_hist_asset_interval_time
            ON price_history(asset_id, interval, ts_utc);

        CREATE TABLE IF NOT EXISTS watchlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_utc TEXT NOT NULL,
            updated_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS watchlist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
            asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
            notes TEXT,
            added_utc TEXT NOT NULL,
            UNIQUE(watchlist_id, asset_id)
        );
        """,
    ),
    (
        2,
        "add normalization audit trail to market_snapshots",
        """
        ALTER TABLE market_snapshots ADD COLUMN normalization_rule TEXT;
        """,
    ),
]


LATEST_VERSION = MIGRATIONS[-1][0]
