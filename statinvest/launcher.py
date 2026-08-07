"""Unified, testable entry point.

Supported modes (only ones that actually exist):
    * ``desktop``   — launch the Tkinter desktop UI.
    * ``streamlit`` — launch the Streamlit UI bound to localhost.
    * ``smoke``     — run the offline smoke test.
    * ``integrity`` — run a database integrity check.
    * ``backup``    — create a verified database backup.

No network listener beyond localhost is opened, and multiple servers are never
started at once.
"""

from __future__ import annotations

import argparse
import sys

from statinvest.config import APP_NAME, APP_SLUG, DISCLAIMER


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_SLUG,
        description=APP_NAME,
        epilog=DISCLAIMER,
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    sub.add_parser("smoke", help="Run the offline smoke test.")

    p_int = sub.add_parser("integrity", help="Run a database integrity check.")
    p_int.add_argument("--db", default=None, help="Path to the SQLite database.")

    p_bak = sub.add_parser("backup", help="Create a verified database backup.")
    p_bak.add_argument("--db", default=None, help="Path to the SQLite database.")

    p_st = sub.add_parser("streamlit", help="Launch the Streamlit UI (localhost).")
    p_st.add_argument("--port", type=int, default=8501)

    sub.add_parser("desktop", help="Launch the Tkinter desktop UI.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.mode == "smoke":
        from smoke_test import run_smoke
        return run_smoke()

    if args.mode == "integrity":
        from statinvest.database.db import Database
        db = Database(args.db)
        db.migrate()
        report = db.integrity_check()
        print(f"Schema version : {report['schema_version']}")
        print(f"Integrity      : {report['integrity']}")
        print(f"FK violations  : {report['foreign_key_violations']}")
        print(f"Row counts     : {report['row_counts']}")
        return 0 if report["ok"] else 1

    if args.mode == "backup":
        from statinvest.database.db import Database
        db = Database(args.db)
        db.migrate()
        try:
            dest = db.backup()
        except FileNotFoundError:
            print("No database file exists yet; nothing to back up.")
            return 1
        print(f"Backup created and verified: {dest}")
        return 0

    if args.mode == "streamlit":
        import subprocess
        from pathlib import Path
        app = Path(__file__).parent / "ui" / "streamlit_app.py"
        # Bind to localhost only; no external interface.
        cmd = [
            sys.executable, "-m", "streamlit", "run", str(app),
            "--server.address", "localhost",
            "--server.port", str(args.port),
            "--server.headless", "true",
        ]
        print(f"Launching Streamlit on http://localhost:{args.port} ...")
        return subprocess.call(cmd)

    if args.mode == "desktop":
        from statinvest.ui.desktop import run_desktop
        return run_desktop()

    parser.error(f"Unknown mode: {args.mode}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
