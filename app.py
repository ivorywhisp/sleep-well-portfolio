"""Sage Invest — a robo-advisor onboarding built the MiFID II way.

Four screens: ① assessment (questionnaire) → ② your investor profile →
③ your portfolio dashboard, with evidence → ④ where it could take you.

Knowledge unlocks products (appropriateness); risk answers set the target
(suitability). The engine behind the recommendation is transparent:
10,000 sampled allocations, filtered by the user's drawdown tolerance,
best CAGR wins, always benchmarked against equal-weight.
"""

import json

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import data, metrics, portfolio, profile, projection, scenarios

# design tokens, taken from the reference aesthetic: cream canvas, white
# cards, sage greens, muted greys, soft red only for negatives
GREEN = "#4F6547"
GREEN_DEEP = "#3C4F36"
GREEN_SOFT = "#9BAF8E"
GREEN_TINT = "#E7EDE2"
INK = "#22271F"
GREY = "#8B9086"
FAINT = "#DDDBD3"
RED = "#B8544B"
RED_TINT = "#F6E4E2"

TIER_EMOJI = {"Beginner": "🌱", "Intermediate": "🌿", "Experienced": "🌳"}
MAX_WEIGHT = 0.40  # concentration guardrail (see help text on fine-tune)

st.set_page_config(page_title="Sage Invest", page_icon="🌿",
                   layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
html, body, [data-testid="stAppViewContainer"] * {
    font-family: 'Plus Jakarta Sans', 'Segoe UI', sans-serif;
}
h1, h2, h3 { font-weight: 700; letter-spacing: -0.02em; }
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFFFF;
    border: 1px solid #F1EFE9;
    border-radius: 20px;
    padding: 0.6rem 0.9rem;
    box-shadow: 0 1px 3px rgba(34, 39, 31, 0.05);
}
.stButton > button {
    border-radius: 12px;
    font-weight: 600;
    padding: 0.55rem 1.3rem;
    border: 1px solid #E4E2DA;
}
[data-testid="stSidebar"] {
    background: #FFFFFF;
    border-right: 1px solid #F1EFE9;
}
.sage-stat {
    background: #FFFFFF; border: 1px solid #F1EFE9; border-radius: 20px;
    padding: 18px 20px; box-shadow: 0 1px 3px rgba(34,39,31,0.05);
}
.sage-stat.dark { background: #5C6E54; border: none; }
.sage-label { font-size: 0.8rem; color: #8B9086; font-weight: 600;
              margin-bottom: 6px; }
.sage-value { font-size: 1.55rem; color: #22271F; font-weight: 800;
              line-height: 1.1; }
.dark .sage-label { color: #DCE4D6; }
.dark .sage-value { color: #FFFFFF; }
.sage-pill { display: inline-block; border-radius: 999px; padding: 2px 10px;
             font-size: 0.72rem; font-weight: 700; margin-left: 8px;
             vertical-align: middle; }
</style>
""", unsafe_allow_html=True)


def stat_card(label: str, value: str, pill: str | None = None,
              positive: bool = True, dark: bool = False) -> str:
    pill_html = ""
    if pill:
        bg, fg = (GREEN_TINT, GREEN) if positive else (RED_TINT, RED)
        if dark:
            bg, fg = "rgba(255,255,255,0.18)", "#FFFFFF"
        pill_html = (f'<span class="sage-pill" style="background:{bg};'
                     f'color:{fg};">{pill}</span>')
    return (f'<div class="sage-stat{" dark" if dark else ""}">'
            f'<div class="sage-label">{label}</div>'
            f'<div class="sage-value">{value}{pill_html}</div></div>')


def style_fig(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=GREY, size=12),
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(gridcolor="#F1EFE9", zeroline=False, linecolor=FAINT)
    fig.update_yaxes(gridcolor="#F1EFE9", zeroline=False, linecolor=FAINT)
    return fig


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


@st.cache_data(show_spinner="Analyzing 10,000 portfolios…")
def cached_table(tickers: tuple[str, ...],
                 window_end: str) -> pd.DataFrame:
    """window_end keys the cache so a fresh data day recomputes."""
    prices, _ = cached_prices(tickers)
    returns = metrics.daily_returns(prices)
    weights = portfolio.sample_weights(len(tickers))
    return portfolio.portfolio_table(returns, weights)


# ------------------------------------------------------------------ sidebar
st.sidebar.title("🌿 Sage Invest")
st.sidebar.caption("Invest at the level you're actually ready for.")
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
    st.title("Invest at the level you're ready for")
    st.markdown(f'<p style="color:{GREY};font-size:1.05rem;">Most '
                'investing apps ask what you want. We first check what '
                "you're ready for.</p>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.markdown(stat_card("Step 1", "A 2-minute assessment",
                          "7 questions"), unsafe_allow_html=True)
    c2.markdown(stat_card("Step 2", "Your investor profile",
                          "MiFID-style"), unsafe_allow_html=True)
    c3.markdown(stat_card("Step 3", "A portfolio, with evidence",
                          "10,000 candidates", dark=True),
                unsafe_allow_html=True)
    st.write("")
    st.markdown(
        "Your knowledge decides **which products** you can access; your "
        "answers on horizon and losses decide **how much risk** fits you. "
        "Scored separately — the way EU regulation makes real advisors "
        "do it. Every recommendation is stress-tested through real crises "
        "and compared against simply splitting your money equally."
    )
    st.button("Start my assessment →", type="primary", on_click=goto,
              args=(1,))

# =================================================================== step 1
elif st.session_state.step == 1:
    st.title("Your assessment")
    st.markdown(f'<p style="color:{GREY};">Two minutes. No wrong answers — '
                'wrong products, only.</p>', unsafe_allow_html=True)

    answers = {}
    complete = True
    for key, q in profile.QUESTIONS.items():
        with st.container(border=True):
            choice = st.radio(f"**{q['text']}**",
                              [label for label, _ in q["options"]],
                              index=None, key=f"q_{key}")
        if choice is None:
            complete = False
        else:
            answers[key] = [label for label, _ in q["options"]].index(choice)

    with st.container(border=True):
        amount = st.number_input("**How much are you investing (€)?**",
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
    st.title("Your investor profile")

    c1, c2, c3 = st.columns(3)
    c1.markdown(stat_card("Product access", f"{TIER_EMOJI[prof.tier]} "
                          f"{prof.tier}",
                          f"knowledge {prof.knowledge_score}/6"),
                unsafe_allow_html=True)
    c2.markdown(stat_card("Risk profile", prof.band,
                          f"suitability {prof.risk_score}/9"),
                unsafe_allow_html=True)
    c3.markdown(stat_card("Loss limit", f"−{prof.tolerance:.0%}",
                          f"~{prof.horizon_years}y horizon", dark=True),
                unsafe_allow_html=True)
    st.write("")

    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("What you can buy")
        for t in data.TIERS[prof.tier]:
            st.markdown(f"- {data.TICKERS[t]}")
        locked = [t for t in data.TICKERS if t not in data.TIERS[prof.tier]]
        if locked:
            st.markdown("**🔒 Locked for now** — products are earned by "
                        "understanding, not appetite:")
            for t in locked:
                st.markdown(f"- {data.TICKERS[t]}")
        else:
            st.markdown("**All products unlocked** — including a Bitcoin "
                        "ETC and a 2x leveraged fund. Understanding them "
                        "is exactly why the next screen still limits how "
                        "much of them you get.")
    with right, st.container(border=True):
        st.subheader("How much risk fits you")
        st.markdown(
            f"We'll only recommend portfolios whose worst historical fall "
            f"stayed within **−{prof.tolerance:.0%}**."
        )
        if prof.capped:
            st.warning(
                "Your answers suggested more appetite, but you need this "
                "money within 3 years — so we capped you at Cautious. "
                "A short horizon can't ride out a bear market, however "
                "brave it feels today."
            )
        st.markdown(f"Projection horizon: **~{prof.horizon_years} years**, "
                    f"from your answer on when you need the money.")

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

    st.title("Your portfolio")
    st.markdown(f'<p style="color:{GREY};">{prof.tier} universe · '
                f'{window[0]} → {window[1]} · max {MAX_WEIGHT:.0%} per '
                'fund</p>', unsafe_allow_html=True)

    if "override_tol" not in st.session_state:
        st.session_state.override_tol = int(prof.tolerance * 100)
    with st.expander("🎛️ Fine-tune (defaults come from your profile)"):
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

    if rec["feasible"]:
        best = rec["row"]
        missed = False
    else:
        # An advisor should guide, not dead-end: show the calmest
        # portfolio available and say plainly why the target was missed.
        best = table.loc[table["max_drawdown"].idxmax()]
        missed = True

    best_weights = np.array([best[f"w_{t}"] for t in tickers])
    best_port = metrics.portfolio_returns(returns, best_weights)
    ew_weights = np.full(len(tickers), 1 / len(tickers))
    ew_port = metrics.portfolio_returns(returns, ew_weights)
    portfolio.save_recommendation(best, list(tickers), window, tolerance)

    if missed:
        st.warning(
            f"**Straight talk:** nothing in your universe stayed within "
            f"−{tolerance:.0%} over this period — the calmest option "
            f"still fell {best['max_drawdown']:.1%}. We're showing that "
            f"calmest portfolio. A real advisor would add cash or "
            f"money-market funds here, which this app's universe "
            f"deliberately excludes."
        )

    # ------------------------------------------------------- stat card row
    recovery = metrics.recovery_days(best_port)
    grown = amount * (1 + best_port).prod()
    ew_ok = ew["max_drawdown"] >= -tolerance
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(stat_card("Historical return", f"{best['cagr']:.1%}/yr",
                          f"{best['cagr'] - ew['cagr']:+.1%} vs 1/N",
                          positive=best["cagr"] >= ew["cagr"]),
                unsafe_allow_html=True)
    c2.markdown(stat_card("Worst episode", f"{best['max_drawdown']:.1%}",
                          "within your limit" if not missed
                          else "limit missed", positive=not missed),
                unsafe_allow_html=True)
    c3.markdown(stat_card("Recovery",
                          f"{recovery} days" if recovery else "ongoing",
                          "from the deepest fall",
                          positive=recovery is not None),
                unsafe_allow_html=True)
    c4.markdown(stat_card(f"€{amount:,.0f} became", f"€{grown:,.0f}",
                          "this window", dark=True),
                unsafe_allow_html=True)
    st.write("")

    # ----------------------------------------------------- allocation + 1/N
    left, right = st.columns([2, 3])
    with left, st.container(border=True):
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
        if ew_ok:
            st.markdown(
                f"**vs equal-weight:** 1/N also stayed within your limit "
                f"(worst {ew['max_drawdown']:.1%}) at {ew['cagr']:.1%}/yr "
                f"— the optimizer "
                f"{'earns' if best['cagr'] > ew['cagr'] else 'does NOT earn'}"
                f" its keep here."
            )
        else:
            st.markdown(
                f"**vs equal-weight:** splitting equally fell "
                f"**{ew['max_drawdown']:.1%}** at its worst — beyond your "
                f"limit. For your profile, 1/N is not a safe default."
            )
    with right, st.container(border=True):
        st.subheader("Every candidate, judged by your limit")
        plot_df = table.copy()
        plot_df["Within limit"] = plot_df["max_drawdown"] >= -tolerance
        fig = px.scatter(plot_df, x="vol", y="cagr", color="Within limit",
                         color_discrete_map={True: GREEN_SOFT,
                                             False: FAINT},
                         labels={"vol": "Annualized volatility",
                                 "cagr": "CAGR"},
                         opacity=0.45, render_mode="webgl")
        fig.add_scatter(x=[ew["vol"]], y=[ew["cagr"]],
                        mode="markers+text",
                        marker=dict(size=12, symbol="diamond", color=GREY),
                        text=["equal-weight"], textposition="top center",
                        name="Equal-weight")
        fig.add_scatter(x=[best["vol"]], y=[best["cagr"]],
                        mode="markers+text",
                        marker=dict(size=16, symbol="star",
                                    color=GREEN_DEEP),
                        text=["yours"], textposition="top center",
                        name="Yours")
        fig.update_layout(yaxis_tickformat=".0%", xaxis_tickformat=".0%",
                          legend_title="")
        st.plotly_chart(style_fig(fig, 380), width="stretch")

    # ------------------------------------------------- drawdowns + scenario
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("The falls you'd have lived through")
        dd_best = (metrics.wealth_curve(best_port)
                   / metrics.wealth_curve(best_port).cummax() - 1)
        dd_ew = (metrics.wealth_curve(ew_port)
                 / metrics.wealth_curve(ew_port).cummax() - 1)
        fig = go.Figure()
        fig.add_scatter(x=dd_ew.index, y=dd_ew, name="Equal-weight",
                        line=dict(color=FAINT, width=1.5))
        fig.add_scatter(x=dd_best.index, y=dd_best, name="Yours",
                        line=dict(color=GREEN, width=2),
                        fill="tozeroy",
                        fillcolor="rgba(79,101,71,0.10)")
        fig.add_hline(y=-tolerance, line_dash="dash", line_color=RED,
                      annotation_text=f"your limit (−{tolerance:.0%})")
        fig.update_layout(yaxis_tickformat=".0%",
                          yaxis_title="Drawdown from peak")
        st.plotly_chart(style_fig(fig, 360), width="stretch")
    with right, st.container(border=True):
        st.subheader("Replay a crisis")
        avail = [k for k in scenarios.STRESS_WINDOWS
                 if scenarios.available(returns, k)]
        unavail = [k for k in scenarios.STRESS_WINDOWS if k not in avail]
        key = st.selectbox("Pick an episode", avail, index=len(avail) - 1)
        st.caption(scenarios.STRESS_WINDOWS[key]["story"])
        rb = scenarios.replay(returns, best_weights, key)
        re_ = scenarios.replay(returns, ew_weights, key)
        fig = go.Figure()
        fig.add_scatter(x=re_.index, y=re_, name="Equal-weight",
                        line=dict(color=FAINT, width=1.5))
        fig.add_scatter(x=rb.index, y=rb, name="Yours",
                        line=dict(color=GREEN, width=2))
        fig.update_layout(yaxis_title="Value of €1 at episode start")
        st.plotly_chart(style_fig(fig, 300), width="stretch")
        if unavail:
            st.caption(f"ℹ️ Not replayable in your tier: "
                       f"{', '.join(unavail)} — its youngest asset only "
                       f"lists from {window[0]}.")

    with st.expander("Under the hood: correlations, pipeline, limitations"):
        cc, qc = st.columns(2)
        with cc:
            fig = px.imshow(returns.corr().round(2), text_auto=True,
                            color_continuous_scale="Greens", zmin=-1,
                            zmax=1)
            st.plotly_chart(style_fig(fig, 380), width="stretch")
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

    rec = json.loads(portfolio.RECOMMENDATION_PATH.read_text())
    weights = np.array(rec["weights"])
    port = metrics.portfolio_returns(returns, weights)

    st.title("Where this could take you")
    st.markdown(f'<p style="color:{GREY};">€{amount:,.0f} · '
                f'{prof.horizon_years} years · 2,000 alternative futures, '
                'built by reshuffling your portfolio\'s own history — '
                'crash days included.</p>', unsafe_allow_html=True)

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
    end = paths.iloc[-1]

    c1, c2, c3 = st.columns(3)
    c1.markdown(stat_card("Median future", f"€{end['p50']:,.0f}",
                          f"in {prof.horizon_years} years", dark=True),
                unsafe_allow_html=True)
    c2.markdown(stat_card("1 in 4 end below", f"€{end['p25']:,.0f}"),
                unsafe_allow_html=True)
    c3.markdown(stat_card("1 in 20 end below", f"€{end['p5']:,.0f}",
                          "above what you put in"
                          if end["p5"] >= amount else "below what you put in",
                          positive=end["p5"] >= amount),
                unsafe_allow_html=True)
    st.write("")

    with st.container(border=True):
        fig = go.Figure()
        fig.add_scatter(x=paths.index, y=paths["p95"], line=dict(width=0),
                        showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=paths.index, y=paths["p5"], fill="tonexty",
                        fillcolor="rgba(79,101,71,0.10)",
                        line=dict(width=0), name="5th–95th percentile")
        fig.add_scatter(x=paths.index, y=paths["p75"], line=dict(width=0),
                        showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=paths.index, y=paths["p25"], fill="tonexty",
                        fillcolor="rgba(79,101,71,0.22)",
                        line=dict(width=0), name="25th–75th percentile")
        fig.add_scatter(x=paths.index, y=paths["p50"],
                        line=dict(color=GREEN_DEEP, width=3),
                        name="Median")
        fig.add_hline(y=amount, line_dash="dot", line_color=GREY,
                      annotation_text="what you put in")
        fig.update_layout(xaxis_title="Years",
                          yaxis_title="Portfolio value (€)")
        st.plotly_chart(style_fig(fig, 430), width="stretch")

    st.markdown(
        f"**Reading it honestly:** if the range above worries you — "
        f"especially the €{end['p5']:,.0f} floor — retake the assessment "
        f"with more honest answers. That's what it's for."
    )
    st.caption(
        "Limitations: futures are drawn from the same distribution as the "
        "past window — no new-crisis imagination, no costs, taxes or "
        "inflation. This is a study project, not investment advice."
    )

    c1, c2 = st.columns([1, 5])
    c1.button("← My portfolio", on_click=goto, args=(3,))
    c2.button("↺ Start over", key="restart_end", on_click=restart)
