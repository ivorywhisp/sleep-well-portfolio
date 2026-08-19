"""Sage Invest — a robo-advisor onboarding built the MiFID II way.

Flow: a one-line welcome → seven questions asked one at a time, big and
tappable → a single results page (profile → portfolio → projection).
Knowledge unlocks products (appropriateness); risk answers set the
target (suitability). The engine is transparent: 10,000 sampled
allocations, filtered by the user's drawdown tolerance, best CAGR wins,
always benchmarked vs equal-weight.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import assistant, data, metrics, portfolio, profile, projection

# design tokens, taken from the reference aesthetic: cream canvas, white
# cards, sage greens, muted greys, soft red only for negatives
GREEN = "#4F6547"
GREEN_DEEP = "#3C4F36"
GREEN_SOFT = "#9BAF8E"
GREEN_TINT = "#E7EDE2"
GREY = "#8B9086"
FAINT = "#DDDBD3"
RED = "#B8544B"
RED_TINT = "#F6E4E2"

TIER_EMOJI = {"Beginner": "🌱", "Intermediate": "🌿", "Experienced": "🌳"}
MAX_WEIGHT = 0.40  # concentration guardrail (see help text on fine-tune)

st.set_page_config(page_title="Sage Invest", page_icon="🌿",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
/* :not(...) guards keep Streamlit's Material icon font intact — a bare *
   selector turns every expander arrow into literal overlapping text */
html, body,
[data-testid="stAppViewContainer"]
  *:not([data-testid="stIconMaterial"]):not(.material-symbols-rounded) {
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
.sage-hero { font-size: 3.2rem; font-weight: 800; letter-spacing: -0.03em;
             line-height: 1.1; color: #22271F; margin: 2.5rem 0 0.8rem; }
.sage-hero-sub { font-size: 1.15rem; color: #8B9086; margin-bottom: 1.6rem;
                 max-width: 34rem; }
.sage-q { font-size: 2rem; font-weight: 800; letter-spacing: -0.02em;
          color: #22271F; margin: 1.6rem 0 1.2rem; max-width: 40rem; }
</style>
""", unsafe_allow_html=True)

QUIZ_CSS = """
<style>
/* answer options only — primary buttons keep the theme's green/white,
   otherwise 'See my portfolio' becomes white text on a white card */
.stButton > button[kind="secondary"] {
    width: 100%;
    text-align: left;
    font-size: 1.06rem;
    padding: 1rem 1.3rem;
    border-radius: 16px;
    background: #FFFFFF;
    border: 1px solid #F1EFE9;
    box-shadow: 0 1px 3px rgba(34,39,31,0.05);
}
.stButton > button[kind="secondary"]:hover {
    border-color: #4F6547; color: #3C4F36;
}
</style>
"""


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
if "view" not in st.session_state:
    st.session_state.view = "welcome"   # welcome -> quiz -> results
    st.session_state.q_index = 0
    st.session_state.answers = {}


def get_api_key() -> str | None:
    """OpenAI key from Streamlit secrets; None hides the chat entirely."""
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return None


# the sidebar exists only as the AI chat on the results page; everywhere
# else (and without a key) it stays hidden so the flow keeps zero chrome
if not (st.session_state.view == "results" and get_api_key()):
    st.markdown('<style>[data-testid="stSidebar"], '
                '[data-testid="collapsedControl"] {display: none;}</style>',
                unsafe_allow_html=True)


def restart() -> None:
    for key in ("view", "q_index", "answers", "profile", "amount",
                "override_tol", "chat"):
        st.session_state.pop(key, None)
    st.session_state.view = "welcome"
    st.session_state.q_index = 0
    st.session_state.answers = {}


def start_quiz() -> None:
    st.session_state.view = "quiz"


def choose(key: str, idx: int) -> None:
    st.session_state.answers[key] = idx
    st.session_state.q_index += 1


def go_back() -> None:
    st.session_state.q_index = max(0, st.session_state.q_index - 1)


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


@st.cache_data(show_spinner="Getting a second opinion (skfolio)…")
def cached_second_opinion(tickers: tuple[str, ...], window_end: str,
                          tol_pct: int) -> np.ndarray:
    """Convex-optimizer benchmark; import deferred so the quiz stays fast."""
    from src import crosscheck
    prices, _ = cached_prices(tickers)
    returns = metrics.daily_returns(prices)
    return crosscheck.second_opinion(returns, tol_pct / 100, MAX_WEIGHT)


# =============================================================== ① welcome
if st.session_state.view == "welcome":
    st.markdown('<div class="sage-hero">Hi 👋<br>Welcome to the future '
                'of investing.</div>', unsafe_allow_html=True)
    st.markdown('<div class="sage-hero-sub">Seven quick questions, and '
                "we'll show you the portfolio you're actually ready for "
                '— with the evidence to prove it.</div>',
                unsafe_allow_html=True)
    st.button("Let's go →", type="primary", on_click=start_quiz)
    st.caption("Built the way EU regulation (MiFID II) makes real "
               "advisors work: your knowledge unlocks products, your "
               "answers set the risk. Educational project — not "
               "investment advice.")

# ================================================================== ② quiz
elif st.session_state.view == "quiz":
    st.markdown(QUIZ_CSS, unsafe_allow_html=True)
    questions = list(profile.QUESTIONS.items())
    i = st.session_state.q_index

    if i < len(questions):
        key, q = questions[i]
        st.progress((i) / (len(questions) + 1),
                    text=f"Question {i + 1} of {len(questions)}")
        st.markdown(f'<div class="sage-q">{q["text"]}</div>',
                    unsafe_allow_html=True)
        mid, _ = st.columns([3, 2])
        with mid:
            for idx, (label, _pts) in enumerate(q["options"]):
                st.button(label, key=f"opt_{key}_{idx}",
                          on_click=choose, args=(key, idx))
        if i > 0:
            st.button("← Back", key="back", on_click=go_back)
    else:
        st.progress(len(questions) / (len(questions) + 1),
                    text="Last step")
        st.markdown('<div class="sage-q">How much are you '
                    'investing?</div>', unsafe_allow_html=True)
        mid, _ = st.columns([2, 3])
        with mid:
            amount = st.number_input("Amount (€)", 1_000, 10_000_000,
                                     50_000, step=1_000,
                                     label_visibility="collapsed")
        if st.button("See my portfolio →", type="primary"):
            st.session_state.profile = profile.score_answers(
                st.session_state.answers)
            st.session_state.amount = amount
            st.session_state.pop("override_tol", None)
            st.session_state.view = "results"
            st.rerun()
        st.button("← Back", key="back_amount", on_click=go_back)

# =============================================================== ③ results
else:
    prof = st.session_state.profile
    amount = st.session_state.amount
    tickers = tuple(data.TIERS[prof.tier])

    head, retake = st.columns([5, 1])
    head.title("Your portfolio")
    retake.button("↺ Retake", on_click=restart)

    # ------------------------------------------------------- profile strip
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
    locked = [t for t in data.TICKERS if t not in tickers]
    if locked:
        st.caption(f"🔒 Locked at your knowledge level: "
                   f"{', '.join(data.TICKERS[t] for t in locked)} — "
                   f"products are earned by understanding, not appetite.")
    else:
        st.caption("All 11 products unlocked — including a Bitcoin ETC "
                   "and a 2x leveraged fund. Your loss limit still "
                   "decides how much of them you get.")
    if prof.capped:
        st.warning("Your answers suggested more appetite, but you need "
                   "this money within 3 years — so we capped you at "
                   "Cautious. A short horizon can't ride out a bear "
                   "market, however brave it feels today.")

    # ------------------------------------------------------------- engine
    prices, source = cached_prices(tickers)
    if source == "snapshot":
        st.info("⚠️ Live download unavailable — using the frozen data "
                f"snapshot (through {prices.index.max().date()}).")
    returns = metrics.daily_returns(prices)
    window = (str(prices.index.min().date()),
              str(prices.index.max().date()))
    coverage_years = len(returns) / metrics.TRADING_DAYS
    if coverage_years < 8:
        st.warning(
            f"**Data coverage:** the youngest fund in your {prof.tier} "
            f"universe only trades since {window[0]}, so every number "
            f"below is tested on {coverage_years:.0f} years of history — "
            f"a window that excludes the 2020 COVID crash and 2008. "
            f"Short windows flatter risky assets; treat a "
            f"'within your limit' verdict with extra skepticism."
        )

    if "override_tol" not in st.session_state:
        st.session_state.override_tol = int(prof.tolerance * 100)
    with st.expander("🎛️ Fine-tune (defaults come from your profile)"):
        tol_pct = st.slider(
            "Drawdown tolerance", 5, 50, step=1, format="-%d%%",
            key="override_tol",
            help="Your profile set this; move it to explore. Everything "
                 "below updates live.")
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
        st.warning(
            f"**Straight talk:** nothing in your universe stayed within "
            f"−{tolerance:.0%} over {window[0]} → {window[1]} — the "
            f"calmest option still fell {best['max_drawdown']:.1%}. "
            f"We're showing that calmest portfolio. A real advisor would "
            f"add cash or money-market funds here."
        )

    best_weights = np.array([best[f"w_{t}"] for t in tickers])
    best_port = metrics.portfolio_returns(returns, best_weights)
    ew_weights = np.full(len(tickers), 1 / len(tickers))
    ew_port = metrics.portfolio_returns(returns, ew_weights)

    # ------------------------------------------------------- verdict cards
    recovery = metrics.recovery_days(best_port)
    grown = amount * (1 + best_port).prod()
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
                          f"{recovery}" if recovery else "ongoing",
                          "trading days to recover" if recovery
                          else "not yet back at peak",
                          positive=recovery is not None),
                unsafe_allow_html=True)
    c4.markdown(stat_card(f"€{amount:,.0f} became", f"€{grown:,.0f}",
                          f"{window[0][:4]}–{window[1][:4]}", dark=True),
                unsafe_allow_html=True)
    st.write("")

    # ------------------------------------------- allocation + drawdown row
    left, right = st.columns([2, 3])
    with left, st.container(border=True):
        st.subheader("Where your money goes")
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
        if ew["max_drawdown"] >= -tolerance:
            st.markdown(
                f"**vs splitting equally:** 1/N also stayed within your "
                f"limit (worst {ew['max_drawdown']:.1%}) at "
                f"{ew['cagr']:.1%}/yr — the optimizer "
                f"{'earns' if best['cagr'] > ew['cagr'] else 'does NOT earn'}"
                f" its keep here."
            )
        else:
            st.markdown(
                f"**vs splitting equally:** 1/N fell "
                f"**{ew['max_drawdown']:.1%}** at its worst — beyond your "
                f"limit. For your profile it is not a safe default."
            )
        st.caption("**When to rebalance:** once a year, or when any fund "
                   "drifts more than 5 points from target — rebalancing "
                   "more often has historically added costs, not safety.")
    with right, st.container(border=True):
        st.subheader("The falls you'd have lived through")
        dd_best = (metrics.wealth_curve(best_port)
                   / metrics.wealth_curve(best_port).cummax() - 1)
        dd_ew = (metrics.wealth_curve(ew_port)
                 / metrics.wealth_curve(ew_port).cummax() - 1)
        fig = go.Figure()
        fig.add_scatter(x=dd_ew.index, y=dd_ew, name="Splitting equally",
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

    # ---------------------------------------------------------- projection
    st.subheader(f"Where this could take €{amount:,.0f} in "
                 f"{prof.horizon_years} years")
    window_years = len(best_port) / metrics.TRADING_DAYS
    sample_cagr = metrics.cagr(best_port)
    if prof.horizon_years > window_years:
        st.warning(
            f"**Extrapolation alert:** your horizon "
            f"({prof.horizon_years} years) is longer than the data behind "
            f"this portfolio ({window_years:.0f} years averaging "
            f"{sample_cagr:.0%}/year). The simulation can only reshuffle "
            f"those years, so treat the upper paths as 'if the recent "
            f"past repeats forever', not as a forecast. Long-run "
            f"diversified equity returns have historically been nearer "
            f"7–9% per year."
        )
    paths = projection.simulate(best_port, amount, prof.horizon_years)
    end = paths.iloc[-1]
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
        st.plotly_chart(style_fig(fig, 400), width="stretch")
        st.markdown(
            f"2,000 futures built by reshuffling this portfolio's own "
            f"history, crash days included. Median: "
            f"**€{end['p50']:,.0f}**. One in twenty ends below "
            f"**€{end['p5']:,.0f}** — "
            f"{'still above' if end['p5'] >= amount else 'below'} what "
            f"you put in. If that floor worries you, retake the "
            f"assessment with more honest answers — that's what it's for."
        )

    # ------------------------------------------------- evidence, on demand
    with st.expander("📋 Evidence: method, correlations, pipeline, "
                     "limitations"):
        sc, cc = st.columns(2)
        with sc:
            st.markdown("**Every candidate we considered**")
            plot_df = table.copy()
            plot_df["Within limit"] = plot_df["max_drawdown"] >= -tolerance
            fig = px.scatter(plot_df, x="vol", y="cagr",
                             color="Within limit",
                             color_discrete_map={True: GREEN_SOFT,
                                                 False: FAINT},
                             labels={"vol": "Annualized volatility",
                                     "cagr": "CAGR",
                                     "sharpe": "Sharpe"},
                             hover_data={"sharpe": ":.2f"},
                             opacity=0.45, render_mode="webgl")
            fig.add_scatter(x=[ew["vol"]], y=[ew["cagr"]],
                            mode="markers+text",
                            marker=dict(size=12, symbol="diamond",
                                        color=GREY),
                            text=["equal-weight"],
                            textposition="top center", name="Equal-weight")
            fig.add_scatter(x=[best["vol"]], y=[best["cagr"]],
                            mode="markers+text",
                            marker=dict(size=16, symbol="star",
                                        color=GREEN_DEEP),
                            text=["yours"], textposition="top center",
                            name="Yours")
            fig.update_layout(yaxis_tickformat=".0%",
                              xaxis_tickformat=".0%", legend_title="")
            st.plotly_chart(style_fig(fig, 340), width="stretch")
            st.markdown("**Asset correlations (daily returns)**")
            fig = px.imshow(returns.corr().round(2), text_auto=True,
                            color_continuous_scale="Greens", zmin=-1,
                            zmax=1)
            st.plotly_chart(style_fig(fig, 340), width="stretch")
        with cc:
            st.markdown(
                f"**Method** — {len(table):,} random long-only "
                f"allocations (max {MAX_WEIGHT:.0%} per fund) over your "
                f"{len(tickers)}-asset universe; keep those whose worst "
                f"historical fall stayed within your limit; recommend "
                f"the highest-CAGR survivor. Drawdown constraints are "
                f"non-convex, so transparent sampling beats a black-box "
                f"optimizer at this asset count.\n\n"
                f"**Pipeline** — Yahoo Finance adjusted closes "
                f"({source} mode); common window starts {window[0]}, "
                f"the first date every asset in your tier trades; "
                f"exchange-holiday gaps forward-filled up to 3 days; "
                f"longer gaps dropped, never invented.\n\n"
                f"**Limitations** — past drawdowns underestimate future "
                f"ones (no 2008 in this window); costs and taxes "
                f"excluded; rebalancing to constant weights assumed; "
                f"picking the best of 10,000 candidates is in-sample "
                f"selection on one realized history; the projection "
                f"resamples days independently (no volatility "
                f"clustering), which understates long-tail risk, and it "
                f"cannot imagine new kinds of crisis.\n\n"
                f"**Verification** — `verify.py` recomputes the "
                f"recommendation's return, volatility and worst fall "
                f"from raw data with fully independent code; agreement "
                f"to 4 decimals is required."
            )
        st.markdown("**Second opinion — skfolio (convex optimizer, "
                    "seen in class)**")
        try:
            sk_w = cached_second_opinion(tickers, window[1], tol_pct)
            sk_port = metrics.portfolio_returns(returns, sk_w)
            sk_cagr = metrics.cagr(sk_port)
            sk_dd = metrics.max_drawdown(sk_port)
            st.markdown(
                f"skfolio's `MeanRisk` solves a convex relaxation of the "
                f"same problem (its drawdown constraint is measured on "
                f"non-compounded wealth) — maximize return under your "
                f"loss limit and the {MAX_WEIGHT:.0%} cap. It lands at "
                f"**{sk_cagr:.1%}/yr** with a worst fall of "
                f"**{sk_dd:.1%}** (measured with our own compounded "
                f"metrics), vs our sampled **{best['cagr']:.1%}/yr**. "
                + ("Near-identical — evidence our sampled answer is "
                   "close to optimal."
                   if abs(sk_cagr - best["cagr"]) < 0.02 else
                   "The optimizer earns its extra return by piling "
                   "assets at their caps (a corner solution); we display "
                   "the sampled landscape and keep the optimizer as a "
                   "cross-check.")
            )
            compare = pd.DataFrame({
                "Fund": [data.TICKERS[t] for t in tickers],
                "Ours": best_weights,
                "skfolio": sk_w,
            }).sort_values("Ours", ascending=False)
            st.dataframe(
                compare, hide_index=True,
                column_config={
                    "Ours": st.column_config.NumberColumn(
                        format="percent"),
                    "skfolio": st.column_config.NumberColumn(
                        format="percent"),
                },
            )
        except Exception:
            st.caption("skfolio cross-check unavailable in this "
                       "environment — the sampled recommendation above "
                       "is unaffected.")

    st.caption("Data: Yahoo Finance daily adjusted closes, EUR-listed "
               "UCITS ETFs/ETCs. Educational project — not investment "
               "advice.")

    # ---------------------------------------------------- AI chat (sidebar)
    # the brief's optional LLM feature, kept genuinely useful: grounded on
    # THIS user's profile and numbers, so it explains their own result
    api_key = get_api_key()
    if api_key:
        top3 = alloc.head(3)
        chat_context = (
            f"Knowledge tier: {prof.tier} (score "
            f"{prof.knowledge_score}/6). Risk band: {prof.band} — max "
            f"tolerable drawdown -{tolerance:.0%}"
            + (", capped to Cautious by a <3y horizon"
               if prof.capped else "") + ". "
            f"Horizon: ~{prof.horizon_years} years. Amount: €{amount:,.0f}. "
            f"Data window: {window[0]} to {window[1]} (Yahoo Finance, EUR "
            f"UCITS funds). Recommended portfolio: "
            + "; ".join(f"{r.Fund} {r.Weight:.0%}"
                        for r in top3.itertuples()) + " (top 3 of "
            f"{len(tickers)}; max 40% per fund). Historical CAGR "
            f"{best['cagr']:.1%}/yr, worst drawdown "
            f"{best['max_drawdown']:.1%}"
            + (f", recovered in {recovery} trading days" if recovery
               else "") + ". "
            f"Equal-weight benchmark: CAGR {ew['cagr']:.1%}, worst "
            f"drawdown {ew['max_drawdown']:.1%}. Bootstrap projection of "
            f"€{amount:,.0f} over {prof.horizon_years}y: median "
            f"€{end['p50']:,.0f}, 5th percentile €{end['p5']:,.0f}. "
            f"Method: 10,000 random long-only allocations filtered by the "
            f"drawdown limit; best CAGR survivor; skfolio convex optimizer "
            f"as cross-check. Rebalancing guidance: yearly or on 5-point "
            f"drift."
        )
        with st.sidebar:
            st.markdown("### 💬 Ask Sage")
            st.caption("Questions about your result? Sage knows your "
                       "profile and portfolio. Educational, not advice.")
            if "chat" not in st.session_state:
                st.session_state.chat = []
            for msg in st.session_state.chat:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
            if question := st.chat_input("e.g. Why so much gold?"):
                st.session_state.chat.append(
                    {"role": "user", "content": question})
                try:
                    answer = assistant.reply(api_key, chat_context,
                                             st.session_state.chat)
                except Exception:
                    answer = ("Sorry — the assistant is unavailable right "
                              "now. Everything else in the app works "
                              "without it.")
                st.session_state.chat.append(
                    {"role": "assistant", "content": answer})
                st.rerun()
