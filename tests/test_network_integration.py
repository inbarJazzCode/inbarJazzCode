"""Optional network integration test — skipped by default.

Run explicitly with:  ``pytest -m network``  (requires live Yahoo access).
Ordinary test runs never depend on live Yahoo availability.
"""

import pytest

pytestmark = pytest.mark.network


def test_yfinance_live_fetch():
    from statinvest.market.provider import YFinanceProvider
    md = YFinanceProvider(retries=2).fetch("AAPL")
    # We do not assert a specific price; only that a status is reported and no
    # exception escapes the provider.
    assert md.data_status in ("DELAYED", "PARTIAL", "ERROR")
