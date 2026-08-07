import pytest

from statinvest.launcher import build_parser, main


def test_parser_requires_mode():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_modes():
    parser = build_parser()
    for mode in ["smoke", "integrity", "backup", "streamlit", "desktop"]:
        args = parser.parse_args([mode])
        assert args.mode == mode


def test_parser_streamlit_port():
    args = build_parser().parse_args(["streamlit", "--port", "9000"])
    assert args.port == 9000


def test_integrity_mode_runs(tmp_path):
    db = tmp_path / "cli.db"
    rc = main(["integrity", "--db", str(db)])
    assert rc == 0


def test_backup_mode_without_db(tmp_path):
    # No migration/file yet -> backup should report nothing to back up.
    db = tmp_path / "missing.db"
    rc = main(["backup", "--db", str(db)])
    assert rc in (0, 1)


def test_smoke_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("STATINVEST_DATA_DIR", str(tmp_path))
    rc = main(["smoke"])
    assert rc == 0


# ── data directory: renaming the product must not orphan an existing database ──
def test_data_dir_uses_new_slug_on_fresh_install(tmp_path, monkeypatch):
    import importlib

    import statinvest.config as C
    monkeypatch.delenv("STATINVEST_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    importlib.reload(C)
    assert C.data_dir().name == C.APP_SLUG


def test_data_dir_prefers_legacy_dir_that_holds_a_database(tmp_path, monkeypatch):
    import importlib

    import statinvest.config as C
    monkeypatch.delenv("STATINVEST_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    importlib.reload(C)
    legacy = tmp_path / C.LEGACY_SLUGS[0]
    legacy.mkdir(parents=True)
    (legacy / C.DB_FILENAME).write_bytes(b"SQLite format 3\x00")
    assert C.data_dir() == legacy


def test_data_dir_prefers_new_dir_once_it_has_its_own_database(tmp_path, monkeypatch):
    import importlib

    import statinvest.config as C
    monkeypatch.delenv("STATINVEST_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    importlib.reload(C)
    for slug in (C.LEGACY_SLUGS[0], C.APP_SLUG):
        d = tmp_path / slug
        d.mkdir(parents=True)
        (d / C.DB_FILENAME).write_bytes(b"SQLite format 3\x00")
    assert C.data_dir().name == C.APP_SLUG
