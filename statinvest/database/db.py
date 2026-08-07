"""Connection management, migrations, backup and integrity checks.

Reliability choices:
    * ``PRAGMA foreign_keys = ON`` enforced on every connection.
    * WAL journal mode for better concurrent read/write behaviour.
    * Migrations run inside a transaction; failures roll back.
    * A timestamped backup is created (and re-opened to verify) before any
      migration that advances the schema version.
    * Parameterized SQL only — no string-built statements from user input.
"""

from __future__ import annotations

import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from statinvest.config import default_db_path
from statinvest.database.schema import MIGRATIONS


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else default_db_path()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._shared_conn: sqlite3.Connection | None = None
        if str(self.path) == ":memory:":
            # Keep a single shared connection alive for in-memory databases.
            self._shared_conn = self._new_connection()

    def _new_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        if str(self.path) != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    @contextmanager
    def connect(self):
        """Yield a connection; commit on success, rollback on error."""
        if self._shared_conn is not None:
            conn = self._shared_conn
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            return
        conn = self._new_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # -- migrations ----------------------------------------------------------
    def current_version(self) -> int:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    description TEXT,
                    applied_at_utc TEXT NOT NULL
                );
                """
            )
            row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
            return int(row["v"]) if row and row["v"] is not None else 0

    def migrate(self) -> dict:
        """Apply pending migrations, backing up first if the DB already exists.

        Returns a dict describing the outcome, including any backup path.
        """
        start = self.current_version()
        target = MIGRATIONS[-1][0]
        info = {"from_version": start, "to_version": target, "backup_path": None,
                "applied": []}
        if start >= target:
            return info

        # Back up an existing on-disk database before advancing the schema.
        if str(self.path) != ":memory:" and self.path.exists() and start > 0:
            info["backup_path"] = str(self.backup())

        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    description TEXT,
                    applied_at_utc TEXT NOT NULL
                );
                """
            )
            for version, description, sql in MIGRATIONS:
                if version <= start:
                    continue
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_migrations(version, description, applied_at_utc) "
                    "VALUES (?, ?, ?)",
                    (version, description, utc_now_iso()),
                )
                info["applied"].append(version)
        return info

    # -- maintenance ---------------------------------------------------------
    def backup(self, backup_dir: str | Path | None = None) -> Path:
        """Create a timestamped backup copy and verify it can be opened."""
        if str(self.path) == ":memory:":
            raise ValueError("Cannot back up an in-memory database.")
        if not self.path.exists():
            raise FileNotFoundError(f"Database {self.path} does not exist yet.")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target_dir = Path(backup_dir) if backup_dir else self.path.parent / "backups"
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / f"{self.path.stem}.{stamp}.bak"
        # Use SQLite's online backup API for a consistent copy.
        src = self._new_connection()
        try:
            bck = sqlite3.connect(str(dest))
            with bck:
                src.backup(bck)
            bck.close()
        finally:
            src.close()
        # Verify the backup opens and passes a quick integrity check.
        verify = sqlite3.connect(str(dest))
        try:
            ok = verify.execute("PRAGMA integrity_check;").fetchone()[0]
            if ok != "ok":
                raise RuntimeError(f"Backup integrity check failed: {ok}")
        finally:
            verify.close()
        return dest

    def integrity_check(self) -> dict:
        with self.connect() as conn:
            result = conn.execute("PRAGMA integrity_check;").fetchone()[0]
            fk = conn.execute("PRAGMA foreign_key_check;").fetchall()
            counts = {}
            for table in ("assets", "market_snapshots", "price_history",
                          "watchlists", "watchlist_items"):
                try:
                    counts[table] = conn.execute(
                        f"SELECT COUNT(*) AS c FROM {table}"  # fixed identifiers only
                    ).fetchone()["c"]
                except sqlite3.OperationalError:
                    counts[table] = None
        return {
            "integrity": result,
            "ok": result == "ok" and len(fk) == 0,
            "foreign_key_violations": len(fk),
            "row_counts": counts,
            "schema_version": self.current_version(),
        }

    def close(self) -> None:
        if self._shared_conn is not None:
            self._shared_conn.close()
            self._shared_conn = None
