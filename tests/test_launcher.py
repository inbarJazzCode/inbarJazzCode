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
