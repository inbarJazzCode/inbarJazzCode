import pytest

from statinvest.market.normalize import consistent_pe, normalize_price
from statinvest.market.provider import SyntheticProvider, get_provider
from statinvest.market.validate import SymbolError, validate_symbol
from statinvest.service import (
    AnalysisService,
    export_watchlist_csv,
    sanitize_cell,
)


@pytest.mark.parametrize("sym", ["AAPL", "^GSPC", "TEVA.TA", "EURUSD=X", "BTC-USD"])
def test_validate_symbol_accepts_provider_syntax(sym):
    assert validate_symbol(sym) == sym.upper()


@pytest.mark.parametrize("bad", ["", "  ", "a/b", "..", "x" * 50, "ab;rm -rf", "a\x00b"])
def test_validate_symbol_rejects_bad(bad):
    with pytest.raises(SymbolError):
        validate_symbol(bad)


def test_agorot_normalization_only_for_ila():
    n = normalize_price(1500.0, "ILA")
    assert n.normalized_price == 15.0
    assert n.normalized_currency == "ILS"
    assert "divide by 100" in n.rule
    # A USD price is never divided.
    u = normalize_price(1500.0, "USD")
    assert u.normalized_price == 1500.0
    assert u.rule == "passthrough"


def test_pe_consistency_after_normalization():
    n = normalize_price(1500.0, "ILA")  # -> 15 ILS
    pe = consistent_pe(n.normalized_price, eps=1.5)
    assert pe == pytest.approx(10.0)


def test_synthetic_provider_offline_deterministic():
    p = SyntheticProvider()
    a = p.fetch("AAPL")
    b = p.fetch("AAPL")
    assert a.data_status == "SYNTHETIC"
    assert a.normalized_price == b.normalized_price
    assert a.asset_type == "EQUITY"


def test_synthetic_index_has_no_eps():
    md = SyntheticProvider().fetch("^GSPC")
    assert md.asset_type == "INDEX"
    assert md.eps is None and md.trailing_pe is None


def test_service_fetch_and_persist(tmp_path):
    from statinvest.database.db import Database
    db = Database(tmp_path / "s.db")
    service = AnalysisService(db=db, provider_name="synthetic")
    result = service.fetch_symbol("AAPL", persist=True)
    assert result["persisted"]
    assert result["market_data"]["data_status"] == "SYNTHETIC"
    assert service.repo.count_snapshots("AAPL") == 1


def test_service_status(tmp_path):
    from statinvest.database.db import Database
    db = Database(tmp_path / "s2.db")
    service = AnalysisService(db=db)
    status = service.status()
    assert status["integrity_ok"]
    assert status["schema_version"] >= 1
    # The public status must not leak an absolute local path.
    assert "/" not in status["db_path"]


def test_csv_sanitization():
    assert sanitize_cell("=1+1") == "'=1+1"
    assert sanitize_cell("+HYPERLINK") == "'+HYPERLINK"
    assert sanitize_cell("-2") == "'-2"
    assert sanitize_cell("@x") == "'@x"
    assert sanitize_cell("AAPL") == "AAPL"


def test_export_watchlist_csv_has_header():
    rows = [{"symbol": "AAPL", "notes": "=danger"}]
    csv_text = export_watchlist_csv(rows)
    assert "symbol" in csv_text.splitlines()[0]
    assert "'=danger" in csv_text


def test_get_provider_defaults_synthetic():
    assert get_provider().name == "synthetic"
    with pytest.raises(ValueError):
        get_provider("nope")
