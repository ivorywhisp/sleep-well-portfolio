"""Lakers Advisor — a robo-advisor onboarding built the MiFID II way.

Four screens: ① tryout (questionnaire) → ② your player profile →
③ your portfolio, with evidence → ④ where it could take you.

Knowledge unlocks products (appropriateness); risk answers set the target
(suitability). The engine behind the recommendation is transparent:
10,000 sampled allocations, filtered by the user's drawdown tolerance,
best CAGR wins, always benchmarked against equal-weight.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import data, metrics, portfolio, profile, projection, scenarios

PURPLE, GOLD, GREY = "#552583", "#FDB927", "#d3d3d3"
TIER_EMOJI = {"Rookie": "🏀", "Starter": "⭐", "MVP": "👑"}
MAX_WEIGHT = 0.40  # concentration guardrail (see help text on override)

st.set_page_config(page_title="Lakers Advisor", page_icon="🏀",
                   layout="wide")


# ------------------------------------------------------------ state helpers
if "step" not in st.session_state:
    st.session_state.step = 0


def goto(step: int) -> None:
    st.session_state.step = step


def restart() -> None:
    for key in ("step", "answers", "profile", "amount", "override_tol"):
        st.session_state.pop(key, None)
    st.session_state.step = 0


# ------------------------------------------------------------ cached engine
@st.cache_data(ttl=3600, show_spinner="Loading market data…")
def cached_prices(tickers: tuple[str, ...]) -> tuple[pd.DataFrame, str]:
    return data.load_prices(list(tickers))


@st.cache_data(show_spinner="Simulating 10,000 portfolios…")
def cached_table(tickers: tuple[str, ...],
                 window_end: str) -> pd.DataFrame:
    """window_end keys the cache so a fresh data day recomputes."""
    prices, _ = cached_prices(tickers)
    returns = metrics.daily_returns(prices)
    weights = portfolio.sample_weights(len(tickers))
    return portfolio.portfolio_table(returns, weights)


# ------------------------------------------------------------------ sidebar
st.sidebar.title("🏀 Lakers Advisor")
st.sidebar.caption("From Rookie to MVP — investing at the level "
                   "you're actually ready for.")
st.sidebar.markdown("---")
st.sidebar.caption(
    "Knowledge unlocks products; risk answers set the target — the same "
    "two-assessment logic MiFID II requires of EU brokers.\n\n"
    "Data: Yahoo Finance daily adjusted closes, EUR-listed UCITS "
    "ETFs/ETCs. Educational project — not investment advice."
)
if st.session_state.step > 0:
    st.sidebar.button("↺ Start over", on_click=restart)


# =================================================================== step 0
if st.session_state.step == 0:
    st.title("🏀 Lakers Advisor")
    st.subheader("Most investing apps ask what you want. "
                 "We first check what you're ready for.")
    st.markdown(
        "- **A 2-minute tryout** — seven questions about your experience "
        "and your nerves.\n"
        "- **Your player profile** — what you may buy (knowledge) and how "
        "much risk fits you (suitability), scored separately, the way EU "
        "regulation (MiFID II) makes real advisors do it.\n"
        "- **A portfolio with evidence** — built from 10,000 candidate "
        "allocations on real market history, stress-tested through real "
        "crises, and always compared against just splitting your money "
        "equally."
    )
    st.button("Start the tryout →", type="primary", on_click=goto, args=(1,))

# =================================================================== step 1
elif st.session_state.step == 1:
    st.title("The tryout")
    st.caption("No wrong answers — wrong products, only.")

    answers = {}
    complete = True
    for key, q in profile.QUESTIONS.items():
        choice = st.radio(q["text"], [label for label, _ in q["options"]],
                          index=None, key=f"q_{key}")
        if choice is None:
            complete = False
        else:
            answers[key] = [label for label, _ in q["options"]].index(choice)

    amount = st.number_input("How much are you investing (€)?",
                             1_000, 10_000_000, 50_000, step=1_000)

    if st.button("See my profile →", type="primary", disabled=not complete):
        st.session_state.answers = answers
        st.session_state.profile = profile.score_answers(answers)
        st.session_state.amount = amount
        st.session_state.pop("override_tol", None)
        goto(2)
        st.rerun()
    if not complete:
        st.caption("Answer all seven questions to continue.")

# =================================================================== step 2
elif st.session_state.step == 2:
    prof = st.session_state.profile
    st.title(f"{TIER_EMOJI[prof.tier]} You're a **{prof.tier}** — "
             f"**{prof.band}** risk")

    left, right = st.columns(2)
    with left:
        st.subheader("What you can buy")
        st.markdown(f"Knowledge & experience score: "
                    f"**{prof.knowledge_score}/6** → tier "
                    f"**{prof.tier}**")
        for t in data.TIERS[prof.tier]:
            st.markdown(f"- {data.TICKERS[t]}")
        locked = [t for t in data.TICKERS if t not in data.TIERS[prof.tier]]
        if locked:
            st.markdown("**🔒 Locked for now** (products should be earned "
                        "by understanding, not appetite):")
            for t in locked:
                st.markdown(f"- {data.TICKERS[t]}")
        else:
            st.markdown("**👑 Full court unlocked** — including Bitcoin ETC "
                        "and a 2x leveraged fund. Understanding them is "
                        "exactly why the next screen still limits how much "
                        "of them you get.")
    with right:
        st.subheader("How much risk fits you")
        st.markdown(
            f"Suitability score: **{prof.risk_score}/9** → "
            f"**{prof.band}**: portfolios whose worst historical fall "
            f"stayed within **−{prof.tolerance:.0%}**."
        )
        if prof.capped:
            st.warning(
                "Your answers suggested more appetite, but you need this "
                "money within 3 years — so we capped you at Cautious. "
                "A short horizon can't ride out a bear market, however "
                "brave it feels today."
            )
        st.markdown(f"Projection horizon: **~{prof.horizon_years} years** "
                    f"(from your answer on when you need the money).")

    c1, c2 = st.columns([1, 5])
    c1.button("← Retake", on_click=restart)
    c2.button("Build my portfolio →", type="primary", on_click=goto,
              args=(3,))

# =================================================================== step 3
elif st.session_state.step == 3:
    prof = st.session_state.profile
    amount = st.session_state.amount
    tickers = tuple(data.TIERS[prof.tier])

    prices, source = cached_prices(tickers)
    if source == "snapshot":
        st.info("⚠️ Live download unavailable — using the frozen data "
                f"snapshot (through {prices.index.max().date()}).")
    returns = metrics.daily_returns(prices)
    window = (str(prices.index.min().date()),
              str(prices.index.max().date()))

    if "override_tol" not in st.session_state:
        st.session_state.override_tol = int(prof.tolerance * 100)
    with st.expander("🎛️ Coach override (defaults come from your profile)"):
        tol_pct = st.slider(
            "Drawdown tolerance", 5, 50, step=1, format="-%d%%",
            key="override_tol",
            help="Your profile set this; move it to explore. The "
                 "recommendation updates live.")
    tolerance = tol_pct / 100

    table = cached_table(tickers, window[1])
    weight_cols = [f"w_{t}" for t in tickers]
    table = table[table[weight_cols].max(axis=1) <= MAX_WEIGHT]
    ew = portfolio.equal_weight_row(returns)
    rec = portfolio.recommend(table, tolerance)

    st.title("Your portfolio — with the evidence")
    st.caption(f"{prof.tier} universe · window {window[0]} → {window[1]} "
               f"· {len(table):,} candidate allocations "
               f"(max {MAX_WEIGHT:.0%} per fund)")

    if rec["feasible"]:
        best = rec["row"]
    else:
        # An advisor should guide, not dead-end: show the calmest
        # portfolio available and say plainly why the target was missed.
        best = table.loc[table["max_drawdown"].idxmax()]
        st.warning(
            f"**Straight talk:** nothing in your universe stayed within "
            f"−{tolerance:.0%} over this period — the calmest option "
            f"still fell {best['max_drawdown']:.1%}. We're showing that "
            f"calmest portfolio. A real advisor would add cash or "
            f"money-market funds here, which this app's universe "
            f"deliberately excludes."
        )

    best_weights = np.array([best[f"w_{t}"] for t in tickers])
    best_port = metrics.portfolio_returns(returns, best_weights)
    ew_weights = np.full(len(tickers), 1 / len(tickers))
    ew_port = metrics.portfolio_returns(returns, ew_weights)
    portfolio.save_recommendation(best, list(tickers), window, tolerance)

    left, right = st.columns([3, 2])
    with left:
        st.subheader("The verdict")
        recovery = metrics.recovery_days(best_port)
        st.markdown(
            f"Best allocation within your limit: "
            f"**{best['cagr']:.1%}/year**, worst episode "
            f"**{best['max_drawdown']:.1%}**"
            + (f", recovered in {recovery} trading days" if recovery else "")
            + f". €{amount:,.0f} would have grown to "
            f"**€{amount * (1 + best_port).prod():,.0f}** over this window."
        )
        if ew["max_drawdown"] >= -tolerance:
            st.markdown(
                f"**vs equal-weight:** 1/N also stayed within your limit "
                f"(worst {ew['max_drawdown']:.1%}) returning "
                f"{ew['cagr']:.1%}/year — the optimizer "
                f"{'earns' if best['cagr'] > ew['cagr'] else 'does NOT earn'}"
                f" its keep here."
            )
        else:
            st.markdown(
                f"**vs equal-weight:** splitting equally would have fallen "
                f"**{ew['max_drawdown']:.1%}** — beyond your limit. For "
                f"your profile, 1/N is not a safe default."
            )
    with right:
        st.subheader("Allocation")
        alloc = pd.DataFrame({
            "Fund": [data.TICKERS[t] for t in tickers],
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

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Every candidate, judged by your limit")
        plot_df = table.copy()
        plot_df["Within limit"] = plot_df["max_drawdown"] >= -tolerance
        fig = px.scatter(plot_df, x="vol", y="cagr", color="Within limit",
                         color_discrete_map={True: PURPLE, False: GREY},
                         labels={"vol": "Annualized volatility",
                                 "cagr": "CAGR"},
                         opacity=0.4, render_mode="webgl")
        fig.add_scatter(x=[ew["vol"]], y=[ew["cagr"]], mode="markers+text",
                        marker=dict(size=13, symbol="diamond",
                                    color="#888888"),
                        text=["equal-weight"], textposition="top center",
                        name="Equal-weight")
        fig.add_scatter(x=[best["vol"]], y=[best["cagr"]],
                        mode="markers+text",
                        marker=dict(size=17, symbol="star", color=GOLD,
                                    line=dict(width=1, color=PURPLE)),
                        text=["yours"], textposition="top center",
                        name="Yours")
        fig.update_layout(yaxis_tickformat=".0%", xaxis_tickformat=".0%",
                          legend_title="", height=400)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.subheader("The falls you'd have lived through")
        dd_best = (metrics.wealth_curve(best_port)
                   / metrics.wealth_curve(best_port).cummax() - 1)
        dd_ew = (metrics.wealth_curve(ew_port)
                 / metrics.wealth_curve(ew_port).cummax() - 1)
        fig = go.Figure()
        fig.add_scatter(x=dd_ew.index, y=dd_ew, name="Equal-weight",
                        line=dict(color="#888888"))
        fig.add_scatter(x=dd_best.index, y=dd_best, name="Yours",
                        line=dict(color=GOLD))
        fig.add_hline(y=-tolerance, line_dash="dash", line_color=PURPLE,
                      annotation_text=f"your limit (−{tolerance:.0%})")
        fig.update_layout(yaxis_tickformat=".0%", height=400,
                          yaxis_title="Drawdown from peak")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Replay a crisis")
    avail = [k for k in scenarios.STRESS_WINDOWS
             if scenarios.available(returns, k)]
    unavail = [k for k in scenarios.STRESS_WINDOWS if k not in avail]
    if unavail:
        st.caption(f"ℹ️ Not replayable in your tier: {', '.join(unavail)} — "
                   f"its youngest asset only lists from {window[0]}.")
    key = st.selectbox("Pick an episode", avail,
                       index=len(avail) - 1)
    st.caption(scenarios.STRESS_WINDOWS[key]["story"])
    rb = scenarios.replay(returns, best_weights, key)
    re_ = scenarios.replay(returns, ew_weights, key)
    fig = go.Figure()
    fig.add_scatter(x=re_.index, y=re_, name="Equal-weight",
                    line=dict(color="#888888"))
    fig.add_scatter(x=rb.index, y=rb, name="Yours",
                    line=dict(color=GOLD))
    fig.update_layout(yaxis_title="Value of €1 at episode start",
                      height=360)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Under the hood: correlations, pipeline, limitations"):
        cc, qc = st.columns(2)
        with cc:
            fig = px.imshow(returns.corr().round(2), text_auto=True,
                            color_continuous_scale="RdBu_r", zmin=-1,
                            zmax=1)
            fig.update_layout(height=380)
            st.plotly_chart(fig, use_container_width=True)
        with qc:
            st.markdown(
                f"- Source: Yahoo Finance adjusted closes ({source} "
                f"mode)\n"
                f"- Common window starts {window[0]} — the first date "
                f"every asset in YOUR tier trades\n"
                f"- Exchange-holiday gaps forward-filled up to 3 days; "
                f"longer gaps dropped, never invented\n"
                f"- Max drawdown = deepest peak-to-trough fall; the risk "
                f"an investor actually feels\n"
                f"- Past drawdowns underestimate future ones (no 2008 "
                f"here); costs and taxes excluded\n"
                f"- `verify.py` recomputes the recommendation's numbers "
                f"from raw data with independent code"
            )

    c1, c2 = st.columns([1, 5])
    c1.button("← My profile", on_click=goto, args=(2,))
    c2.button("Where could this take me? →", type="primary",
              on_click=goto, args=(4,))

# =================================================================== step 4
else:
    prof = st.session_state.profile
    amount = st.session_state.amount
    tickers = tuple(data.TIERS[prof.tier])
    prices, _ = cached_prices(tickers)
    returns = metrics.daily_returns(prices)

    import json
    rec = json.loads(portfolio.RECOMMENDATION_PATH.read_text())
    weights = np.array(rec["weights"])
    port = metrics.portfolio_returns(returns, weights)

    st.title(f"€{amount:,.0f}, {prof.horizon_years} years, "
             f"2,000 alternative futures")
    st.caption("Bootstrap simulation: we reshuffle your portfolio's own "
               "historical daily returns into thousands of possible "
               "futures — keeping the crash days the past actually had.")

    window_years = len(port) / metrics.TRADING_DAYS
    sample_cagr = metrics.cagr(port)
    if prof.horizon_years > window_years:
        st.warning(
            f"**Extrapolation alert:** your horizon "
            f"({prof.horizon_years} years) is longer than the data behind "
            f"this portfolio ({window_years:.0f} years averaging "
            f"{sample_cagr:.0%}/year — an unusually "
            f"{'good' if sample_cagr > 0.09 else 'specific'} stretch). "
            f"The simulation can only reshuffle those years, so treat the "
            f"upper paths as 'if the recent past repeats forever', not as "
            f"a forecast. Long-run diversified equity returns have "
            f"historically been nearer 7–9% per year."
        )
    paths = projection.simulate(port, amount, prof.horizon_years)
    fig = go.Figure()
    fig.add_scatter(x=paths.index, y=paths["p95"], line=dict(width=0),
                    showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=paths.index, y=paths["p5"], fill="tonexty",
                    fillcolor="rgba(85,37,131,0.15)", line=dict(width=0),
                    name="5th–95th percentile")
    fig.add_scatter(x=paths.index, y=paths["p75"], line=dict(width=0),
                    showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=paths.index, y=paths["p25"], fill="tonexty",
                    fillcolor="rgba(85,37,131,0.35)", line=dict(width=0),
                    name="25th–75th percentile")
    fig.add_scatter(x=paths.index, y=paths["p50"],
                    line=dict(color=GOLD, width=3), name="Median")
    fig.add_hline(y=amount, line_dash="dot", line_color="#888888",
                  annotation_text="what you put in")
    fig.update_layout(xaxis_title="Years", yaxis_title="Portfolio value (€)",
                      height=460)
    st.plotly_chart(fig, use_container_width=True)

    end = paths.iloc[-1]
    st.markdown(
        f"**Reading it honestly:** the median future puts you at "
        f"**€{end['p50']:,.0f}**. One in four futures ends below "
        f"€{end['p25']:,.0f}; one in twenty below **€{end['p5']:,.0f}** — "
        f"and {'that is still above' if end['p5'] >= amount else 'that is below'} "
        f"what you put in. If that last number scares you, retake the "
        f"tryout with more honest answers — that's what it's for."
    )
    st.caption(
        "Limitations: futures are drawn from the same distribution as the "
        "past window — no new-crisis imagination, no costs, taxes or "
        "inflation. This is a study project, not investment advice."
    )

    c1, c2 = st.columns([1, 5])
    c1.button("← My portfolio", on_click=goto, args=(3,))
    c2.button("↺ Start over", key="restart_end", on_click=restart)
