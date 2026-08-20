# Sage Invest 🌿

**Live app:** https://lakersteam.streamlit.app/
**Team Lakers** — Daniel Gallinas · Martin Christian Herisson · Vasileios Konstantakopoulos · Greta Allison Perbellini
IENYC · Python for Finance · Final Project

## The user and the decision

A **European retail investor opening their first (or next) investment account** who must decide: *"Which portfolio should I buy, given what I actually understand and what losses I can actually sit through?"*

Sage Invest answers it the way EU regulation (MiFID II) obliges real advisors to:

- an **appropriateness** score (knowledge & experience, 3 questions) decides **which products** the app may recommend — Beginner (6 broad UCITS index funds), Intermediate (+ Nasdaq-100, EU property, world small caps), Experienced (+ a Bitcoin ETC and a 2x-leveraged equity fund). Appetite never unlocks products; understanding does.
- a **suitability** score (horizon, loss tolerance, capacity, goal, 4 questions) sets **how much risk** the recommendation targets, expressed as the maximum historical drawdown the user says they could hold through (−10% to −35%). A horizon under 3 years overrides everything down to Cautious.

## How the recommendation is built

1. 10,000 random long-only allocations (Dirichlet-sampled, max 40% per fund) over the user's unlocked universe.
2. For each: CAGR, volatility, Sharpe, and **maximum drawdown** — the loss an investor actually feels.
3. Keep the allocations whose worst historical episode stayed inside the user's limit; recommend the highest-CAGR survivor.
4. Always benchmarked against **equal-weight (1/N)** — judged by the same drawdown test, so the comparison is informative, not ceremonial.
5. A **bootstrap Monte Carlo** (2,000 resampled futures of the portfolio's own daily returns) projects the outcome range to the user's horizon, with an explicit extrapolation warning when the horizon exceeds the data window.
6. Cross-check: **skfolio**'s `MeanRisk` optimizer solves a convex relaxation of the same constrained problem (its drawdown constraint is measured on non-compounded wealth); its answer is compared to ours in the Evidence panel.

Why sampling instead of only an optimizer: a max-drawdown constraint is non-convex; sampling is transparent, shows the user the whole feasible landscape, and avoids presenting corner solutions (everything piled at the caps) as advice. The optimizer remains as an independent check.

## Data provenance

- **Source:** Yahoo Finance daily **adjusted closes** via `yfinance`, retrieved live on each session (cached 1h).
- **Instruments:** 11 EUR-listed UCITS ETFs/ETCs (Euronext Amsterdam & Xetra) — see `src/data.py::TICKERS`.
- **Fallback + verification input:** `data/snapshot.csv` — a frozen copy (2014-08-18 → 2026-08-18, raw per-ticker history) used automatically if the live download fails, and as the deterministic input for independent verification.
- **Cleaning policy** (documented in `src/data.py`): per-universe common window (starts at the youngest asset's first trading day), exchange-holiday gaps forward-filled up to 3 days, longer gaps dropped — never invented.

## Run it locally

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Optional AI chat: create `.streamlit/secrets.toml` with `OPENAI_API_KEY = "..."` (never commit it — it is gitignored). Without a key the chat simply doesn't appear; everything else works.

## Verification

- `python make_recommendation.py && python verify.py` — the first command regenerates `data/recommended.json` deterministically from the frozen snapshot (fixed seed, demo profile); the second recomputes that portfolio's CAGR, volatility and max drawdown **from the raw snapshot with zero imports from `src/`** and requires 4-decimal agreement. Output: `verification_evidence.txt`. During development this check caught a real off-by-one window bug.
- `python test_wizard.py` — drives the entire app headlessly (Streamlit AppTest) for two personas, asserting no screen raises.
- Edge case handled and shown in-app: a loss limit stricter than anything history offers → the app explains the gap and shows the calmest portfolio instead of failing.

## Honest limitations

Past drawdowns underestimate future ones (the window excludes 2008). Costs, taxes and inflation are excluded. Constant-weight rebalancing is assumed (guidance in-app: yearly or on 5-point drift). The projection reshuffles the past; it cannot imagine new kinds of crisis. Educational project — not investment advice.

## AI use

See [AI_USE_DISCLOSURE.md](AI_USE_DISCLOSURE.md).

---

*Repository: `sage-invest`. The product is Sage Invest, by team Lakers.*
