import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_data_dir(monkeypatch):
    """Redirect the application-data directory to a temp path for every test."""
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("STATINVEST_DATA_DIR", tmp)
        yield Path(tmp)


@pytest.fixture
def tmp_db(tmp_path):
    from statinvest.database.db import Database
    db = Database(tmp_path / "test.db")
    db.migrate()
    yield db
    db.close()
