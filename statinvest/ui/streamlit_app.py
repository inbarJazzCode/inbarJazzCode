"""Streamlit UI for the Statistics & Investment Eco-System.

Launch via the unified launcher: ``python main.py streamlit`` (binds to
localhost). This module keeps all persistence in the shared service layer so a
logical action is never saved twice, and it labels data provenance explicitly.
"""

from __future__ import annotations

import numpy as np

from statinvest.config import APP_NAME, DISCLAIMER, MULTI_ASSET_EXAMPLES, TA125_PRESET


def _run():  # pragma: no cover - requires the Streamlit runtime
    import streamlit as st

    from statinvest.models.linear import OLSModel
    from statinvest.models.logistic import LogisticModel
    from statinvest.models.poisson import PoissonModel
    from statinvest.service import AnalysisService, export_watchlist_csv

    st.set_page_config(page_title="Statistics & Investment Eco-System", layout="wide")
    st.title(APP_NAME)
    st.caption(DISCLAIMER)

    if "service" not in st.session_state:
        provider = st.sidebar.selectbox("Data provider", ["synthetic", "yfinance"], index=0)
        st.session_state.service = AnalysisService(provider_name=provider)
    service = st.session_state.service

    status = service.status()
    with st.sidebar:
        st.subheader("Database")
        st.write(f"Schema version: {status['schema_version']}")
        st.write(f"Integrity OK: {status['integrity_ok']}")
        st.write(f"Rows: {status['row_counts']}")
        st.info("Availability depends on Yahoo/yfinance coverage. TA-125 is a preset, "
                "not the full scope.")

    tab_market, tab_models, tab_watch = st.tabs(
        ["Market data", "Model lab", "Watchlist"]
    )

    with tab_market:
        st.subheader("Fetch a symbol")
        col1, col2 = st.columns([2, 1])
        symbol = col1.text_input("Symbol", value="AAPL")
        preset = col2.selectbox("Preset", ["(none)", "TA-125", "Multi-asset examples"])
        if preset == "TA-125":
            st.write("TA-125 preset:", ", ".join(TA125_PRESET))
        elif preset == "Multi-asset examples":
            st.write("Examples:", ", ".join(MULTI_ASSET_EXAMPLES))
        if st.button("Fetch & save"):
            result = service.fetch_symbol(symbol, persist=True, with_history=True)
            md = result["market_data"]
            badge = {
                "LIVE": "🟢 LIVE", "DELAYED": "🟡 DELAYED", "CACHED": "🔵 CACHED",
                "SYNTHETIC": "⚪ SYNTHETIC", "PARTIAL": "🟠 PARTIAL", "ERROR": "🔴 ERROR",
            }.get(md["data_status"], md["data_status"])
            st.write(f"**Status:** {badge}  |  **Saved:** {result['persisted']}")
            st.json({k: md[k] for k in (
                "symbol", "asset_type", "normalized_price", "normalized_currency",
                "raw_price", "raw_currency", "eps", "trailing_pe", "normalization_rule")})

    with tab_models:
        st.subheader("Model laboratory")
        family = st.selectbox("Model family", ["OLS", "Logistic", "Poisson"])
        st.caption("Fit on synthetic demo data with known structure (neutral research view).")
        rng = np.random.default_rng(0)
        n = st.slider("Sample size", 50, 500, 200)
        if st.button("Fit demo model"):
            X = rng.normal(size=(n, 2))
            if family == "OLS":
                y = 1.0 + 2.0 * X[:, 0] - 1.5 * X[:, 1] + rng.normal(scale=0.5, size=n)
                res = OLSModel().fit(X, y, feature_names=["f1", "f2"])
                st.write(f"Formula: y ~ const + f1 + f2  |  R² = {res.r_squared:.3f}")
                st.table(res.coefficient_table())
            elif family == "Logistic":
                z = 0.5 + 1.5 * X[:, 0] - 1.0 * X[:, 1]
                p = 1 / (1 + np.exp(-z))
                y = (rng.uniform(size=n) < p).astype(int)
                res = LogisticModel().fit(X, y, feature_names=["f1", "f2"])
                st.write(f"Converged: {res.converged}  |  McFadden R² = "
                         f"{res.pseudo_r2_mcfadden:.3f}")
                st.table(res.coefficient_table())
            else:
                mu = np.exp(0.2 + 0.5 * X[:, 0])
                y = rng.poisson(mu)
                res = PoissonModel().fit(X, y, feature_names=["f1", "f2"])
                st.write(f"Converged: {res.converged}  |  Dispersion = "
                         f"{res.dispersion:.3f}")
                st.table(res.coefficient_table())
            for w in res.warnings:
                st.warning(w)

    with tab_watch:
        st.subheader("Research watchlist (not investment advice)")
        name = st.text_input("Watchlist name", value="default")
        sym = st.text_input("Add symbol", value="MSFT", key="wl_sym")
        if st.button("Add to watchlist"):
            service.add_to_watchlist(name, sym)
        rows = service.watchlist_view(name)
        if rows:
            st.table(rows)
            st.download_button("Export CSV", export_watchlist_csv(rows),
                               file_name="watchlist.csv", mime="text/csv")
        else:
            st.write("Watchlist is empty.")


if __name__ == "__main__":  # pragma: no cover
    _run()
