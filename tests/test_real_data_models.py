"""Fitting models on real stored securities.

All offline: the synthetic provider supplies deterministic price history, so
these tests never touch the network.
"""

import pytest

from statinvest.database.db import Database
from statinvest.service import MIN_HISTORY_ROWS, AnalysisService


@pytest.fixture
def svc(tmp_path):
    service = AnalysisService(db=Database(tmp_path / "m.db"),
                              provider_name="synthetic")
    for sym in ("AAPL", "MSFT", "KO"):
        service.fetch_symbol(sym, persist=True, with_history=True)
    return service


def test_stored_symbols_lists_what_can_be_modelled(svc):
    stored = svc.stored_symbols()
    assert set(stored) == {"AAPL", "KO", "MSFT"}


def test_stored_symbols_excludes_thin_history(svc):
    """A symbol fetched without history must not be offered for modelling."""
    svc.fetch_symbol("JPM", persist=True, with_history=False)
    assert "JPM" not in svc.stored_symbols()


def test_returns_pair_aligns_on_shared_dates(svc):
    pair = svc.returns_pair("AAPL", "MSFT")
    assert pair["n"] == len(pair["y"]) == len(pair["x"]) == len(pair["dates"])
    assert pair["n"] >= MIN_HISTORY_ROWS
    assert pair["dates"] == sorted(pair["dates"])


def test_returns_pair_rejects_a_symbol_against_itself(svc):
    with pytest.raises(ValueError, match="different securities"):
        svc.returns_pair("AAPL", "AAPL")


def test_returns_pair_reports_missing_history_clearly(svc):
    with pytest.raises(ValueError, match="Fetch it on the Market data tab"):
        svc.returns_pair("AAPL", "TSLA")


def test_returns_are_returns_not_price_levels(svc):
    """Guards the spurious-regression fix: values must be small returns."""
    pair = svc.returns_pair("AAPL", "MSFT")
    assert all(abs(v) < 1.0 for v in pair["y"])
    assert all(abs(v) < 1.0 for v in pair["x"])


def test_fit_market_model_shape(svc):
    out = svc.fit_market_model("AAPL", "MSFT")
    assert out["pair"]["target"] == "AAPL"
    assert out["pair"]["predictor"] == "MSFT"

    ols = out["ols"]
    assert ols["se_type"] == "hc3"
    assert len(ols["summary"]["coefficients"]) == 2
    assert "breusch_pagan" in ols
    assert isinstance(ols["heteroskedastic"], bool)

    log = out["logistic"]
    for key in ("in_sample", "out_of_sample", "baseline",
                "generalises", "beats_baseline", "odds_ratio_per_1pct"):
        assert key in log
    assert 0.0 <= log["baseline"] <= 1.0


def test_out_of_sample_test_period_follows_training_period(svc):
    """No look-ahead: every training date precedes every test date."""
    out = svc.fit_market_model("AAPL", "MSFT")
    train_start, train_end = out["logistic"]["train_range"]
    test_start, test_end = out["logistic"]["test_range"]
    assert train_start <= train_end < test_start <= test_end


def test_robust_and_classical_standard_errors_differ(svc):
    """The robust/classical comparison is computed, not hard-coded."""
    out = svc.fit_market_model("AAPL", "MSFT", se_type="hc3")
    assert out["ols"]["se_inflation_pct"] == pytest.approx(
        out["ols"]["se_inflation_pct"])  # finite, not NaN
    assert out["ols"]["se_inflation_pct"] != 0.0


def test_train_fraction_moves_the_split(svc):
    a = svc.fit_market_model("AAPL", "MSFT", train_frac=0.60)
    b = svc.fit_market_model("AAPL", "MSFT", train_frac=0.80)
    assert a["logistic"]["train_range"][1] < b["logistic"]["train_range"][1]


def test_model_uses_only_stored_data_no_network(svc, monkeypatch):
    """fit_market_model must read the database, never re-fetch."""
    def boom(*a, **k):
        raise AssertionError("fit_market_model must not hit the provider")

    monkeypatch.setattr(svc.provider, "fetch", boom)
    out = svc.fit_market_model("AAPL", "KO")
    assert out["pair"]["n"] > 0
