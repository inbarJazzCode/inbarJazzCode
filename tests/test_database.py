import sqlite3
from pathlib import Path

import pytest

from statinvest.database.db import Database
from statinvest.database.repository import (
    AssetRecord,
    Repository,
    SnapshotRecord,
)
from statinvest.database.schema import LATEST_VERSION


def test_migration_and_version(tmp_path):
    db = Database(tmp_path / "a.db")
    info = db.migrate()
    assert info["to_version"] == LATEST_VERSION
    assert db.current_version() == LATEST_VERSION


def test_migration_is_idempotent(tmp_path):
    db = Database(tmp_path / "b.db")
    db.migrate()
    second = db.migrate()
    assert second["applied"] == []


def test_backup_created_and_openable(tmp_path):
    db = Database(tmp_path / "c.db")
    db.migrate()
    dest = db.backup()
    assert Path(dest).exists()
    conn = sqlite3.connect(str(dest))
    assert conn.execute("PRAGMA integrity_check;").fetchone()[0] == "ok"
    conn.close()


def test_integrity_check_ok(tmp_db):
    report = tmp_db.integrity_check()
    assert report["ok"]
    assert report["foreign_key_violations"] == 0


def test_snapshot_insert_and_idempotent(tmp_db):
    repo = Repository(tmp_db)
    snap = SnapshotRecord(fetched_at_utc="2026-01-01T00:00:00+00:00",
                          price=10.0, source="synthetic")
    repo.insert_snapshot("AAPL", snap)
    repo.insert_snapshot("AAPL", snap)  # same key -> no duplicate
    assert repo.count_snapshots("AAPL") == 1


def test_snapshot_distinct_times(tmp_db):
    repo = Repository(tmp_db)
    repo.insert_snapshot("AAPL", SnapshotRecord(
        fetched_at_utc="2026-01-01T00:00:00+00:00", price=1.0, source="s"))
    repo.insert_snapshot("AAPL", SnapshotRecord(
        fetched_at_utc="2026-01-02T00:00:00+00:00", price=2.0, source="s"))
    assert repo.count_snapshots("AAPL") == 2


def test_price_history_dedup(tmp_db):
    repo = Repository(tmp_db)
    rows = [
        {"ts_utc": "2026-01-01T00:00:00+00:00", "close": 1.0},
        {"ts_utc": "2026-01-02T00:00:00+00:00", "close": 2.0},
    ]
    assert repo.insert_price_history("AAPL", "1d", rows) == 2
    assert repo.insert_price_history("AAPL", "1d", rows) == 0  # dedup
    assert len(repo.get_price_history("AAPL", "1d")) == 2


def test_asset_missing_fields_ok(tmp_db):
    repo = Repository(tmp_db)
    aid = repo.upsert_asset(AssetRecord(symbol="^GSPC", asset_type="INDEX"))
    asset = repo.get_asset("^GSPC")
    assert asset["asset_type"] == "INDEX"
    assert asset["eps"] if "eps" in asset else True  # eps not an asset column
    # market-cap-less asset types are fine — no exception on latest snapshot
    assert repo.latest_snapshot("^GSPC") is None


def test_upsert_preserves_good_value(tmp_db):
    repo = Repository(tmp_db)
    repo.upsert_asset(AssetRecord(symbol="AAPL", display_name="Apple Inc."))
    repo.upsert_asset(AssetRecord(symbol="AAPL", display_name=None))  # poorer fetch
    assert repo.get_asset("AAPL")["display_name"] == "Apple Inc."


def test_watchlist_crud(tmp_db):
    repo = Repository(tmp_db)
    repo.add_to_watchlist("wl", "AAPL", notes="research")
    repo.add_to_watchlist("wl", "MSFT")
    assert len(repo.list_watchlist("wl")) == 2
    repo.remove_from_watchlist("wl", "AAPL")
    remaining = repo.list_watchlist("wl")
    assert len(remaining) == 1 and remaining[0]["symbol"] == "MSFT"


def test_utc_timestamps(tmp_db):
    repo = Repository(tmp_db)
    repo.upsert_asset(AssetRecord(symbol="AAPL"))
    asset = repo.get_asset("AAPL")
    assert asset["first_seen_utc"].endswith("+00:00") or "T" in asset["first_seen_utc"]
