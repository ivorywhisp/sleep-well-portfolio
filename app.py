"""Sleep-Well Portfolio — a drawdown-first portfolio decision app.

For the risk-averse retail investor, the question is not "what maximizes
return per unit of volatility?" but "what is the best portfolio whose worst
historical episode I could have sat through without panic-selling?".
This app answers that question.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import data, metrics, portfolio, scenarios

st.set_page_config(page_title="Sleep-Well Portfolio", page_icon="😴",
                   layout="wide")


@st.cache_data(ttl=3600, show_spinner="Loading market data…")
def cached_prices(tickers: tuple[str, ...]) -> tuple[pd.DataFrame, str]:
    prices, source = data.load_prices(list(tickers))
    return prices, source


# ---------------------------------------------------------------- sidebar --
st.sidebar.title("😴 Sleep-Well Portfolio")
st.sidebar.caption(
    "Find the best-returning portfolio whose worst historical fall "
    "you could actually have endured."
)

tolerance_pct = st.sidebar.slider(
    "My pain threshold — the portfolio drop that would make me sell",
    min_value=5, max_value=50, value=15, step=1, format="-%d%%",
    help="Your maximum tolerable peak-to-trough loss. The app only "
         "recommends portfolios that stayed inside this limit over the "
         "whole historical sample.",
)
tolerance = tolerance_pct / 100

selected = st.sidebar.multiselect(
    "Investable universe (EUR-listed index funds)",
    options=list(data.TICKERS),
    default=list(data.TICKERS),
    format_func=lambda t: f"{t} — {data.TICKERS[t]}",
)

max_weight_pct = st.sidebar.slider(
    "Concentration limit — max weight in any single fund",
    min_value=20, max_value=100, value=40, step=5, format="%d%%",
    help="A realistic retail guardrail: without it, drawdown-constrained "
         "optimization tends to pile into whichever single asset had the "
         "luckiest decade (a form of hindsight overfitting).",
)

amount = st.sidebar.number_input("Amount to invest (€)", 1_000, 10_000_000,
                                 50_000, step=1_000)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Data: Yahoo Finance daily adjusted closes (auto-retrieved; frozen "
    "snapshot as fallback). Educational project — not investment advice."
)

if len(selected) < 4:
    st.warning("Pick at least four assets — the brief (and diversification) "
               "require it.")
    st.stop()

# ---------------------------------------------------------------- pipeline --
prices, source = cached_prices(tuple(selected))
if source == "snapshot":
    st.info("⚠️ Live download unavailable — using the frozen data snapshot "
            f"shipped with the app (through {prices.index.max().date()}).")

# window is stated in PRICE dates: verify.py re-derives returns from prices,
# so a returns-based window would silently drop the first trading day
returns = metrics.daily_returns(prices)
window = (str(prices.index.min().date()), str(prices.index.max().date()))

weights_matrix = portfolio.sample_weights(len(selected))
table = portfolio.portfolio_table(returns, weights_matrix)
ew = portfolio.equal_weight_row(returns)

# apply the concentration guardrail before judging feasibility
weight_cols = [f"w_{t}" for t in selected]
table = table[table[weight_cols].max(axis=1) <= max_weight_pct / 100]
if table.empty:
    st.warning("The concentration limit is tighter than any sampled "
               "allocation — raise it a little.")
    st.stop()
rec = portfolio.recommend(table, tolerance)

# ---------------------------------------------------------------- header ---
st.title("Could you have held on?")
st.caption(f"Analysis window: {window[0]} → {window[1]} · "
           f"{len(returns):,} trading days · "
           f"{len(table):,} candidate allocations within the "
           f"{max_weight_pct}% concentration limit")

if not rec["feasible"]:
    st.error(
        f"**No portfolio in this universe stayed within −{tolerance_pct}% "
        f"over this period.** The calmest candidate still fell "
        f"{rec['closest_drawdown']:.1%} at its worst. Either raise your "
        f"threshold above {abs(rec['closest_drawdown']):.0%}, or accept "
        f"that this goal needs assets (like cash or short-term bonds) "
        f"outside the current universe."
    )
    st.stop()

best = rec["row"]
best_weights = np.array([best[f"w_{t}"] for t in selected])
best_port = metrics.portfolio_returns(returns, best_weights)
ew_weights = np.full(len(selected), 1 / len(selected))
ew_port = metrics.portfolio_returns(returns, ew_weights)

portfolio.save_recommendation(best, selected, window, tolerance)

# ---------------------------------------------------------------- verdict --
left, right = st.columns([3, 2])

with left:
    st.subheader("The recommendation")
    rec_recovery = metrics.recovery_days(best_port)
    st.markdown(
        f"Out of **{len(table):,}** candidate allocations, "
        f"**{rec['n_feasible']:,}** kept their worst fall within your "
        f"−{tolerance_pct}% threshold. The best of them returned "
        f"**{best['cagr']:.1%}/year** with a worst episode of "
        f"**{best['max_drawdown']:.1%}**"
        + (f", recovered in {rec_recovery} trading days"
           if rec_recovery else "")
        + f". €{amount:,.0f} invested would have grown to "
        f"**€{amount * (1 + best_port).prod():,.0f}**."
    )
    ew_feasible = ew["max_drawdown"] >= -tolerance
    if ew_feasible:
        st.markdown(
            f"**Equal-weight comparison:** splitting equally also stayed "
            f"within your threshold (worst fall {ew['max_drawdown']:.1%}) "
            f"but returned {ew['cagr']:.1%}/year — "
            f"{'less' if ew['cagr'] < best['cagr'] else 'more'} than the "
            f"recommendation."
        )
    else:
        st.markdown(
            f"**Equal-weight comparison:** splitting your money equally "
            f"would have fallen **{ew['max_drawdown']:.1%}** at its worst — "
            f"beyond what you said you could endure. For you, 1/N is not "
            f"a safe default."
        )

with right:
    st.subheader("Recommended allocation")
    alloc = pd.DataFrame({
        "Fund": [data.TICKERS[t] for t in selected],
        "Weight": best_weights,
        "Amount (€)": best_weights * amount,
    }).sort_values("Weight", ascending=False)
    st.dataframe(
        alloc, hide_index=True,
        column_config={
            "Weight": st.column_config.ProgressColumn(
                format="percent", min_value=0, max_value=1),
            "Amount (€)": st.column_config.NumberColumn(format="€%.0f"),
        },
    )

# ------------------------------------------------------------------ charts --
st.markdown("---")
scatter_col, dd_col = st.columns(2)

with scatter_col:
    st.subheader("Every candidate, judged by your threshold")
    plot_df = table.copy()
    plot_df["Within my threshold"] = plot_df["max_drawdown"] >= -tolerance
    fig = px.scatter(
        plot_df, x="vol", y="cagr", color="Within my threshold",
        color_discrete_map={True: "#2E86AB", False: "#d3d3d3"},
        labels={"vol": "Annualized volatility", "cagr": "CAGR"},
        opacity=0.4, render_mode="webgl",
    )
    fig.add_scatter(x=[ew["vol"]], y=[ew["cagr"]], mode="markers+text",
                    marker=dict(size=14, symbol="diamond", color="#F18F01"),
                    text=["equal-weight"], textposition="top center",
                    name="Equal-weight")
    fig.add_scatter(x=[best["vol"]], y=[best["cagr"]], mode="markers+text",
                    marker=dict(size=16, symbol="star", color="#C73E1D"),
                    text=["recommended"], textposition="top center",
                    name="Recommended")
    fig.update_layout(yaxis_tickformat=".0%", xaxis_tickformat=".0%",
                      legend_title="", height=420)
    st.plotly_chart(fig, use_container_width=True)

with dd_col:
    st.subheader("The falls you would have lived through")
    dd_best = (metrics.wealth_curve(best_port)
               / metrics.wealth_curve(best_port).cummax() - 1)
    dd_ew = (metrics.wealth_curve(ew_port)
             / metrics.wealth_curve(ew_port).cummax() - 1)
    fig = go.Figure()
    fig.add_scatter(x=dd_ew.index, y=dd_ew, name="Equal-weight",
                    line=dict(color="#F18F01"))
    fig.add_scatter(x=dd_best.index, y=dd_best, name="Recommended",
                    line=dict(color="#C73E1D"))
    fig.add_hline(y=-tolerance, line_dash="dash", line_color="black",
                  annotation_text=f"your limit (−{tolerance_pct}%)")
    fig.update_layout(yaxis_tickformat=".0%", height=420,
                      yaxis_title="Drawdown from peak")
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------- stress test --
st.subheader("Replay a crisis")
scenario_key = st.selectbox(
    "Watch both portfolios live through a named episode",
    options=list(scenarios.STRESS_WINDOWS),
    index=2,
)
spec = scenarios.STRESS_WINDOWS[scenario_key]
st.caption(spec["story"])
replay_best = scenarios.replay(returns, best_weights, scenario_key)
replay_ew = scenarios.replay(returns, ew_weights, scenario_key)
fig = go.Figure()
fig.add_scatter(x=replay_ew.index, y=replay_ew, name="Equal-weight",
                line=dict(color="#F18F01"))
fig.add_scatter(x=replay_best.index, y=replay_best, name="Recommended",
                line=dict(color="#C73E1D"))
fig.update_layout(yaxis_title="Value of €1 at episode start", height=380)
st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------------------- evidence ---
with st.expander("Under the hood: correlations, data quality, limitations"):
    corr_col, quality_col = st.columns(2)
    with corr_col:
        st.markdown("**Asset correlations (daily returns)**")
        fig = px.imshow(returns.corr().round(2), text_auto=True,
                        color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
        fig.update_layout(height=380)
        st.plotly_chart(fig, use_container_width=True)
    with quality_col:
        st.markdown("**Pipeline decisions**")
        st.markdown(
            f"- Source: Yahoo Finance adjusted closes ({source} mode)\n"
            f"- Common window starts {window[0]} (first date all selected "
            f"assets trade)\n"
            f"- Exchange-holiday gaps forward-filled up to 3 days "
            f"(German listings close ~25 days/decade while Amsterdam trades)\n"
            f"- Longer gaps dropped, never invented\n"
        )
        st.markdown("**Honest limitations**")
        st.markdown(
            "- Past drawdowns underestimate future ones; this sample "
            "excludes 2008.\n"
            "- Metrics assume rebalancing to constant weights; taxes and "
            "trading costs are ignored.\n"
            "- 10,000 samples cover but do not exhaust the allocation "
            "space.\n"
            "- An independent script (`verify.py`) recomputes the "
            "recommendation's CAGR and drawdown from raw data."
        )
