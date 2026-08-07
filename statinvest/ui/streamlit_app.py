"""Streamlit UI for the Statistics & Investment Eco-System.

Launch via the unified launcher: ``python main.py streamlit`` (binds to
localhost). All persistence goes through the shared service layer so a logical
action is never saved twice, and data provenance is labelled explicitly.
"""

from __future__ import annotations

import numpy as np

from statinvest.config import APP_NAME, DISCLAIMER, MULTI_ASSET_EXAMPLES, TA125_PRESET

STATUS_BADGE = {
    "LIVE": "🟢 LIVE", "DELAYED": "🟡 DELAYED", "CACHED": "🔵 CACHED",
    "SYNTHETIC": "⚪ SYNTHETIC", "PARTIAL": "🟠 PARTIAL", "ERROR": "🔴 ERROR",
}


def _brand(st, icon_path):  # pragma: no cover - requires the Streamlit runtime
    """Branded header: logo, product name, byline, disclaimer."""
    import base64
    from pathlib import Path

    from statinvest.config import __version__

    logo = Path(icon_path).with_name("statinvest_logo.png")
    src = logo if logo.exists() else Path(icon_path)
    b64 = ""
    if src.exists():
        b64 = base64.b64encode(src.read_bytes()).decode()

    img = (f'<img src="data:image/png;base64,{b64}" alt="Investment Eco-System logo" '
           f'style="width:74px;height:74px;border-radius:16px;flex:none;'
           f'box-shadow:0 4px 14px rgba(0,80,160,.28)">') if b64 else ""

    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:18px;padding:6px 0 14px;
                    border-bottom:1px solid rgba(128,150,165,.28);margin-bottom:18px;">
          {img}
          <div style="display:flex;flex-direction:column;gap:3px;min-width:0;">
            <div style="font-size:1.55rem;font-weight:700;letter-spacing:-.02em;
                        line-height:1.12;">Investment Eco-System</div>
            <div style="font-size:.95rem;opacity:.72;">
              OLS · Logistic · Poisson &nbsp;—&nbsp; <b>by Inbar</b>
            </div>
            <div style="font-family:ui-monospace,Menlo,monospace;font-size:.68rem;
                        letter-spacing:.12em;text-transform:uppercase;opacity:.5;
                        margin-top:2px;">v{__version__} · research build</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(DISCLAIMER)


def _run():  # pragma: no cover - requires the Streamlit runtime
    import pandas as pd
    import streamlit as st

    from statinvest.models._util import add_intercept
    from statinvest.models.evaluation import chronological_split
    from statinvest.models.linear import OLSModel
    from statinvest.models.logistic import LogisticModel
    from statinvest.models.optim import run_optimizer
    from statinvest.models.poisson import PoissonModel
    from statinvest.service import AnalysisService, export_watchlist_csv

    from pathlib import Path
    _icon = Path(__file__).resolve().parents[2] / "assets" / "statinvest_icon.png"
    st.set_page_config(page_title="Investment Eco-System",
                       page_icon=str(_icon) if _icon.exists() else "📈",
                       layout="wide", initial_sidebar_state="expanded")
    _brand(st, _icon)

    provider = st.sidebar.selectbox(
        "Data provider", ["yahoo-chart", "synthetic", "yfinance"], index=0,
        help="yahoo-chart = live prices and valuation ratios from Yahoo. "
             "synthetic = offline demo data, no internet needed.",
    )
    if "service" not in st.session_state or st.session_state.get("provider") != provider:
        st.session_state.service = AnalysisService(provider_name=provider)
        st.session_state.provider = provider
    service = st.session_state.service

    status = service.status()
    with st.sidebar:
        st.subheader("Database")
        st.write(f"Schema version: {status['schema_version']}")
        st.write(f"Integrity OK: {status['integrity_ok']}")
        st.write(f"Rows: {status['row_counts']}")
        st.info("Coverage depends on Yahoo/yfinance. TA-125 is a preset, not the full scope.")

    tab_market, tab_lab, tab_optim, tab_ai, tab_watch = st.tabs(
        ["📊 Market data", "🧪 Model lab", "⚙️ Estimator comparison",
         "🤖 AI explainer", "⭐ Watchlist"]
    )

    # ── Market data ────────────────────────────────────────────────────────
    with tab_market:
        st.subheader("Fetch a symbol")
        c1, c2 = st.columns([2, 1])
        symbol = c1.text_input("Symbol", value="AAPL")
        preset = c2.selectbox("Preset", ["(none)", "TA-125", "Multi-asset examples"])
        if preset == "TA-125":
            st.write("TA-125 preset:", ", ".join(TA125_PRESET))
        elif preset == "Multi-asset examples":
            st.write("Examples:", ", ".join(MULTI_ASSET_EXAMPLES))

        if st.button("Fetch & save", type="primary"):
            result = service.fetch_symbol(symbol, persist=True, with_history=True)
            st.session_state.last_fetch = result

        result = st.session_state.get("last_fetch")
        if result:
            md = result["market_data"]
            badge = STATUS_BADGE.get(md["data_status"], md["data_status"])
            st.write(f"**Status:** {badge} · **Saved to database:** {result['persisted']}")

            m1, m2, m3, m4 = st.columns(4)
            price = md["normalized_price"]
            m1.metric("Price", f"{price:,.2f} {md['normalized_currency'] or ''}"
                      if price else "—")
            # מכפיל רווח — trailing price/earnings ratio
            pe = md["trailing_pe"]
            m2.metric("מכפיל רווח · P/E (trailing)", f"{pe:.2f}" if pe else "n/a")
            fpe = md["forward_pe"]
            m3.metric("Forward P/E", f"{fpe:.2f}" if fpe else "n/a")
            mc = md["market_cap"]
            m4.metric("Market cap", f"{mc/1e9:,.1f}B" if mc else "n/a")

            if not pe:
                st.info(
                    f"No P/E for **{md['symbol']}** — its asset type is "
                    f"**{md['asset_type'] or 'unknown'}**. Indices, ETFs, currencies and "
                    "crypto have no earnings, so a price/earnings ratio is undefined for "
                    "them. This is correct behaviour, not a missing fetch."
                )
            with st.expander("All fields, including the normalization audit trail"):
                st.json({k: md[k] for k in (
                    "symbol", "display_name", "asset_type", "exchange",
                    "normalized_price", "normalized_currency", "raw_price", "raw_currency",
                    "normalization_rule", "eps", "trailing_pe", "forward_pe",
                    "market_cap", "net_income", "data_status", "source", "fetched_at_utc")})

    # ── Model lab ──────────────────────────────────────────────────────────
    with tab_lab:
        st.subheader("Model laboratory")
        family = st.radio("Model family", ["OLS", "Logistic", "Poisson"],
                          horizontal=True, key="lab_family")
        se_type = "classical"
        if family == "OLS":
            se_type = st.radio(
                "Standard errors", ["classical", "hc0", "hc1", "hc3"],
                horizontal=True, index=3,
                help="HC variants are heteroskedasticity-robust. Financial returns are "
                     "almost always heteroskedastic, so HC3 is the safer default.",
            )
        n = st.slider("Sample size", 50, 1000, 300)
        seed = st.number_input("Random seed", value=0, step=1)

        if st.button("Fit model", type="primary", key="fit_lab"):
            rng = np.random.default_rng(int(seed))
            X = rng.normal(size=(n, 2))
            if family == "OLS":
                y = 1.0 + 2.0 * X[:, 0] - 1.5 * X[:, 1] + rng.normal(scale=0.5, size=n)
                model = OLSModel()
                res = model.fit(X, y, feature_names=["f1", "f2"], se_type=se_type)
                st.write(f"**Formula:** `y ~ const + f1 + f2` · **R²** = {res.r_squared:.4f} "
                         f"· **Adj R²** = {res.adj_r_squared:.4f} · n = {res.n}")
                st.dataframe(pd.DataFrame(res.coefficient_table()), use_container_width=True)
                d1, d2 = st.columns(2)
                d1.write("**VIF (multicollinearity)**")
                d1.json({k: round(v, 3) for k, v in
                         model.variance_inflation_factors().items()})
                bp = model.breusch_pagan()
                d2.write("**Breusch-Pagan (heteroskedasticity)**")
                d2.json({"statistic": round(bp["statistic"], 3),
                         "p_value": round(bp["p_value"], 4)})
                st.caption("True values: const 1.0, f1 2.0, f2 −1.5")
            elif family == "Logistic":
                z = 0.5 + 1.5 * X[:, 0] - 1.0 * X[:, 1]
                y = (rng.uniform(size=n) < 1 / (1 + np.exp(-z))).astype(int)
                model = LogisticModel()
                res = model.fit(X, y, feature_names=["f1", "f2"])
                st.write(f"**Converged:** {res.converged} in {res.n_iter} IRLS iterations · "
                         f"**McFadden R²** = {res.pseudo_r2_mcfadden:.4f}")
                st.dataframe(pd.DataFrame(res.coefficient_table()), use_container_width=True)
                st.json(model.classification_metrics(X, y))
                st.caption("True values: const 0.5, f1 1.5, f2 −1.0")
            else:
                mu = np.exp(0.2 + 0.5 * X[:, 0])
                y = rng.poisson(mu)
                model = PoissonModel()
                res = model.fit(X, y, feature_names=["f1", "f2"])
                st.write(f"**Converged:** {res.converged} · **Dispersion** = "
                         f"{res.dispersion:.3f} · **Deviance** = {res.deviance:.1f}")
                st.dataframe(pd.DataFrame(res.coefficient_table()), use_container_width=True)
                st.caption("True values: const 0.2, f1 0.5. Dispersion ≈ 1 means "
                           "the Poisson assumption holds.")
            for w in res.warnings:
                st.warning(w)

    # ── Estimator comparison: closed form vs SGD vs Adam ───────────────────
    with tab_optim:
        st.subheader("Compare estimation methods on the same data")
        st.caption(
            "The same objective, three different ways of minimising it. The closed-form "
            "solution is the reference; SGD and Adam are iterative and must be judged on "
            "whether they actually converged — not merely on whether the loop finished."
        )
        oc1, oc2, oc3 = st.columns(3)
        objective = oc1.radio("Objective", ["mse (OLS)", "logistic"], horizontal=False)
        lr = oc2.number_input("Learning rate", value=0.05, step=0.01, format="%.4f")
        epochs = oc3.number_input("Epochs", value=400, step=50, min_value=10)
        b1, b2, b3 = st.columns(3)
        batch = b1.selectbox("Batch size", ["full", "64", "32", "16"])
        l2 = b2.number_input("L2 penalty", value=0.0, step=0.01, format="%.3f")
        oseed = b3.number_input("Seed", value=0, step=1, key="opt_seed")

        methods = st.multiselect(
            "Methods to run", ["Closed form / IRLS", "SGD", "Adam"],
            default=["Closed form / IRLS", "SGD", "Adam"],
        )

        if st.button("Run comparison", type="primary"):
            rng = np.random.default_rng(int(oseed))
            nobs = 400
            Xr = rng.normal(size=(nobs, 2))
            obj = "mse" if objective.startswith("mse") else "logistic"
            if obj == "mse":
                true = np.array([1.0, 2.0, -1.5])
                y = true[0] + Xr @ true[1:] + rng.normal(scale=0.5, size=nobs)
            else:
                true = np.array([0.5, 1.5, -1.0])
                z = true[0] + Xr @ true[1:]
                y = (rng.uniform(size=nobs) < 1 / (1 + np.exp(-z))).astype(float)
            Xd = add_intercept(Xr)
            bs = None if batch == "full" else int(batch)

            rows, traces = [], {}
            reference = None
            if "Closed form / IRLS" in methods:
                if obj == "mse":
                    ref = OLSModel().fit(Xr, y, feature_names=["f1", "f2"])
                    reference = ref.params
                    rows.append({"method": "Closed form (QR/SVD)", "converged": True,
                                 "iterations": 1,
                                 "const": reference[0], "f1": reference[1],
                                 "f2": reference[2], "max |Δ| vs reference": 0.0})
                else:
                    ref = LogisticModel().fit(Xr, y, feature_names=["f1", "f2"])
                    reference = ref.params
                    rows.append({"method": "IRLS (Newton)", "converged": ref.converged,
                                 "iterations": ref.n_iter,
                                 "const": reference[0], "f1": reference[1],
                                 "f2": reference[2], "max |Δ| vs reference": 0.0})
            for name in ("SGD", "Adam"):
                if name not in methods:
                    continue
                r = run_optimizer(Xd, y, objective=obj, optimizer=name.lower(),
                                  lr=float(lr), epochs=int(epochs), batch_size=bs,
                                  l2=float(l2), seed=int(oseed), reference=reference)
                traces[name] = r.loss_trace
                rows.append({"method": name, "converged": r.converged,
                             "iterations": r.n_iter,
                             "const": r.params[0], "f1": r.params[1], "f2": r.params[2],
                             "max |Δ| vs reference": r.max_coef_diff})
                for w in r.warnings:
                    st.warning(f"**{name}:** {w}")

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)
            st.caption(f"True coefficients — const {true[0]}, f1 {true[1]}, f2 {true[2]}")
            if traces:
                st.write("**Loss per epoch** (lower is better; a flat tail means it stopped "
                         "improving)")
                maxlen = max(len(v) for v in traces.values())
                st.line_chart(pd.DataFrame(
                    {k: list(v) + [None] * (maxlen - len(v)) for k, v in traces.items()}))
            st.info(
                "A completed loop is not the same as convergence. If a method shows "
                "`converged = False`, or a large gap against the reference, its "
                "coefficients should not be interpreted — regardless of how the loss looks."
            )

    # ── AI explainer (optional) ────────────────────────────────────────────
    with tab_ai:
        from statinvest.assistant import (
            FREE_BACKENDS, AssistantConfig, AssistantError, build_facts,
            describe_payload, explain,
        )

        st.subheader("Explain results in plain language")
        st.caption(
            "Optional. Off unless you configure it. The assistant only puts the numbers "
            "into words — every figure is still computed by this app's own estimators."
        )

        backend = st.selectbox("Backend", list(FREE_BACKENDS.keys()), index=3)
        base_url, default_model = FREE_BACKENDS[backend]
        bc1, bc2 = st.columns(2)
        base_url = bc1.text_input("Base URL (OpenAI-compatible)", value=base_url)
        model_name = bc2.text_input("Model", value=default_model)
        cfg = AssistantConfig(base_url=base_url, model=model_name)

        s = cfg.status()
        if s["local"]:
            st.success(
                f"Local backend — no API key needed and **nothing leaves your computer**. "
                f"Make sure the server is running at `{base_url}`."
            )
        elif s["key_present"]:
            st.success(f"API key found in `{s['key_env_var']}`. Ready.")
        else:
            st.warning(
                f"No API key set. Provide one in the `{s['key_env_var']}` environment "
                "variable before starting the app — for example:\n\n"
                f"```\nWindows:  set {s['key_env_var']}=your-key-here\n"
                f"Mac/Linux: export {s['key_env_var']}=your-key-here\n```\n"
                "The key is read from the environment only. It is never written to the "
                "database, never committed to Git and never displayed here."
            )

        st.divider()
        demo = st.radio("Explain which result?",
                        ["A weak model (low R², fails out-of-sample)",
                         "A strong model"], horizontal=False)
        if demo.startswith("A weak"):
            facts = build_facts(
                {"family": "ols", "target": "KO daily return",
                 "features": ["S&P 500 daily return"], "formula": "r_KO ~ const + r_SPX",
                 "n_observations": 1254},
                {"family": "ols", "n": 1254, "r_squared": 0.0728, "se_type": "hc3",
                 "coefficients": [
                     {"term": "const", "coef": 0.000381, "std_err": 0.000290, "p_value": 0.190},
                     {"term": "r_SPX", "coef": 0.2634, "std_err": 0.0389, "p_value": 2e-11}],
                 "warnings": ["Residuals are heteroskedastic; HC3 errors used."]},
                extra={"out_of_sample_roc_auc": 0.436, "in_sample_roc_auc": 0.686,
                       "majority_baseline": 0.5066,
                       "note": "chronological 70/30 split, no shuffling"})
        else:
            facts = build_facts(
                {"family": "ols", "target": "NVDA daily return",
                 "features": ["S&P 500 daily return"], "formula": "r_NVDA ~ const + r_SPX",
                 "n_observations": 1254},
                {"family": "ols", "n": 1254, "r_squared": 0.5078, "se_type": "hc3",
                 "coefficients": [
                     {"term": "const", "coef": 0.00135, "std_err": 0.00065, "p_value": 0.037},
                     {"term": "r_SPX", "coef": 2.1714, "std_err": 0.0640, "p_value": 1.9e-179}],
                 "warnings": []},
                extra={"out_of_sample_roc_auc": 0.815, "in_sample_roc_auc": 0.843,
                       "majority_baseline": 0.5358,
                       "note": "alpha p=0.037 does not survive Bonferroni across 5 tests"})

        with st.expander("Exactly what would be sent (nothing else leaves your machine)"):
            st.code(describe_payload(facts), language="json")
            st.caption(
                "An allow-list, not a filter: only the fields listed above are ever "
                "transmitted. No database contents, file paths, watchlists or personal data."
            )

        if st.button("Explain these results", type="primary", disabled=not cfg.enabled):
            with st.spinner("Asking the model…"):
                try:
                    out = explain(facts, cfg)
                    st.markdown(f"> {out.text}")
                    st.caption(f"Generated by `{out.model}` · commentary only, "
                               "not a computation")
                except AssistantError as exc:
                    st.error(str(exc))

        st.info(
            "**Cost note.** A paid API is fine to start with. When you want a free "
            "option, switch the backend above to **Ollama** or **LM Studio** and run a "
            "model on your own machine — the protocol is identical, so nothing else in "
            "the app changes, and your data stops leaving the computer entirely."
        )

    # ── Watchlist ──────────────────────────────────────────────────────────
    with tab_watch:
        st.subheader("Research watchlist")
        st.caption("Neutral research view. A lower P/E is not a buy signal — it requires "
                   "further analysis. Not investment advice.")
        name = st.text_input("Watchlist name", value="default")
        sym = st.text_input("Add symbol", value="MSFT", key="wl_sym")
        if st.button("Add to watchlist"):
            service.add_to_watchlist(name, sym)
        rows = service.watchlist_view(name)
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            st.download_button("Export CSV", export_watchlist_csv(rows),
                               file_name="watchlist.csv", mime="text/csv")
        else:
            st.write("Watchlist is empty.")


if __name__ == "__main__":  # pragma: no cover
    _run()
