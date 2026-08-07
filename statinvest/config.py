"""Central configuration: names, paths, disclaimers, constants.

The application stores its SQLite database in a project-controlled
application-data directory rather than a random working directory. The
location can be overridden safely for tests via the ``STATINVEST_DATA_DIR``
environment variable or by passing an explicit path to the database layer.
"""

from __future__ import annotations

import os
from pathlib import Path

__version__ = "1.0.0"

# Human-facing product name. Everything user-visible derives from these two.
APP_NAME = "Invest-System — OLS, Logistic & Poisson"
# Filesystem / repository-safe slug.
APP_SLUG = "invest-system"

# Directory names used by earlier releases. Kept only so an existing database
# is still found after the product was renamed; never written to fresh.
LEGACY_SLUGS = ("statistics-investment-eco-system",)

DISCLAIMER = (
    "Educational / research use only. Market data may be delayed and depends on "
    "third-party provider (Yahoo/yfinance) coverage. This is not investment advice. "
    "No brokerage integration, order placement or automated trading is provided."
)

# Default database filename inside the application-data directory.
DB_FILENAME = "statinvest.db"

# TA-125 is preserved as an important preset and educational use case, but the
# application is intentionally not limited to it.
TA125_PRESET = [
    "^TA125.TA",  # Tel Aviv 125 index
    "TEVA.TA",
    "NICE.TA",
    "POLI.TA",
    "LUMI.TA",
]

# A small, clearly labelled multi-asset example set for testing and demos.
# This is an *example* set, not a claim of a complete market universe.
MULTI_ASSET_EXAMPLES = [
    "AAPL",        # equity (USD)
    "MSFT",        # equity (USD)
    "^GSPC",       # index
    "SPY",         # ETF
    "EURUSD=X",    # currency
    "BTC-USD",     # crypto
    "TEVA.TA",     # Tel Aviv equity (ILA/agorot quoting)
]


def data_dir() -> Path:
    """Return the application-data directory, creating it if needed.

    Resolution order:
      1. ``STATINVEST_DATA_DIR`` environment variable (used by tests).
      2. ``~/.local/share/invest-system`` (XDG-ish default).
      3. A legacy directory from an earlier product name, if it still holds a
         database and the current one does not — so renaming the product never
         orphans a user's existing data.
    """
    override = os.environ.get("STATINVEST_DATA_DIR")
    if override:
        path = Path(override).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path

    base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    path = base / APP_SLUG

    # The slug has changed across releases. If the current directory has no
    # database yet but an older one does, keep using the older one rather than
    # silently starting from an empty database.
    if not (path / DB_FILENAME).exists():
        for legacy in LEGACY_SLUGS:
            old = base / legacy
            if (old / DB_FILENAME).exists():
                return old

    path.mkdir(parents=True, exist_ok=True)
    return path


def default_db_path() -> Path:
    """Return the default SQLite database path."""
    return data_dir() / DB_FILENAME
