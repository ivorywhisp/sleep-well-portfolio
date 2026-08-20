# Sage Invest: team walkthrough and Q&A pack

Read this before the demo. Each of us owns a slice, but the professor can ask anyone about any part. The rule of this project is simple: knowledge unlocks products, risk answers set the target, and every headline number has independent proof behind it.

Suggested slices: Daniel (product and demo), Martin (data pipeline), Vasileios (method and metrics), Greta (verification and limitations).

## How the code is organized

- `app.py`: the whole user interface. Three views held in session state: welcome, quiz (one question at a time), results. No math lives here; it calls the modules below and draws cards and charts.
- `src/profile.py`: the questionnaire and its scoring. Three knowledge questions produce a score out of 6 that maps to a product tier. Reaching Experienced requires BOTH having used complex products AND answering the leverage concept check correctly. Four suitability questions produce a score out of 9 that maps to a loss limit band. A horizon under 3 years forces Cautious regardless of the other answers.
- `src/data.py`: tickers, tiers, download, cleaning, snapshot. Cleaning policy: per universe common window, forward fill gaps up to 3 days (exchange holidays), drop longer gaps. The counts of filled cells and dropped dates travel with the data and are shown in the app.
- `src/metrics.py`: CAGR, annualized volatility, Sharpe, maximum drawdown, recovery days. All from daily returns, 252 trading days per year, risk free rate assumed zero.
- `src/portfolio.py`: the engine. 10,000 random long only allocations (Dirichlet), computed in chunks for memory, filtered by a 40% per fund cap and the user's drawdown limit, best CAGR survivor recommended, equal weight always computed as the benchmark.
- `src/projection.py`: bootstrap simulation. 2,000 alternative futures built by resampling the portfolio's own daily returns with replacement.
- `src/crosscheck.py`: skfolio MeanRisk, maximizing return under a drawdown cap and the weight cap. A convex relaxation of our problem, used as a second opinion.
- `src/assistant.py`: the Ask Sage chat. OpenAI behind Streamlit secrets, grounded on the user's numbers, educational only.
- `verify.py`: independent recomputation of the recommendation's CAGR, volatility and worst fall from the raw snapshot. It imports nothing from `src/`. Agreement to 4 decimals required.
- `make_recommendation.py`: regenerates the committed recommendation deterministically from the snapshot, so evidence and recommendation never drift apart.
- `test_wizard.py`: drives the full app headlessly for three personas, including the edge case where nothing satisfies the limit.

## Vocabulary you must be able to define

- **CAGR**: compound annual growth rate. The single yearly rate that turns the starting value into the ending value over the period.
- **Maximum drawdown**: the deepest fall from a previous peak, as a percentage. The loss an investor actually feels and the risk measure our whole product is built on.
- **Sharpe ratio**: mean return divided by volatility, annualized. We compute it and show it on hover, but we do not select on it, because our user's stated constraint is a loss limit, not volatility.
- **Dirichlet sampling**: a way to draw random weight vectors that are non negative and sum to one, uniformly over that space.
- **Bootstrap**: building simulated futures by resampling observed returns with replacement. Keeps fat tails, loses volatility clustering.
- **In sample vs out of sample**: numbers measured on the data used to choose the portfolio vs on data the choice never saw. Ours: chosen on the first six years, the pick made 8.7% per year in sample but 6.5% out of sample with a worst fall of 17.4%, past the 15% limit. The app shows this.
- **MiFID II appropriateness vs suitability**: EU rule. Appropriateness tests knowledge and experience and gates complex products. Suitability matches the investment to goals, horizon and loss capacity. We implement both, separately.

## The twenty questions we expect, with answers

1. **Why random sampling instead of a proper optimizer?** A maximum drawdown cap on compounded wealth is not convex, so classic solvers do not apply directly. Sampling is transparent and shows the whole feasible landscape. We also run a real convex optimizer (skfolio) as a cross check: at low risk it lands where we land; at high risk it wins only by piling funds at their caps, corner solutions we would not present as advice.
2. **Isn't picking the best of 10,000 on one history just data mining?** Partly, yes, and we measure it instead of hiding it: selecting on the first half of history only, the pick's return dropped from 8.7% to 6.5% per year on the unseen half and its worst fall exceeded the limit. That out of sample gap is displayed in the app's Evidence panel.
3. **Why does knowledge unlock products instead of risk appetite?** Because appetite without understanding is how people buy leveraged funds they cannot explain. This mirrors MiFID II: brokers must test knowledge before granting access to complex products, and suitability separately. Our Experienced tier requires both hands on experience with complex products and a correct answer to the leverage question.
4. **Your riskiest tier has the shortest data. Isn't that backwards?** It is a real limitation and the app says so to the user: the Bitcoin ETC lists in June 2020, so that universe's window never saw the COVID crash. We warn rather than certify. A production version would backfill with index proxies or refuse feasibility verdicts on short windows.
5. **Why maximum drawdown and not volatility?** Volatility punishes upside and downside equally. Our user's real constraint is the fall that makes them sell everything. Drawdown is the risk they experience.
6. **What does the 40% cap do?** Without it, drawdown constrained selection piles into whichever single asset had the luckiest decade (early versions recommended 68% gold). It is a concentration guardrail, like real funds have.
7. **What if no portfolio meets the user's limit?** The app says so plainly, shows the calmest portfolio available, and explains that a real advisor would add cash or money market funds, which our universe deliberately excludes. This path is covered by an automated test.
8. **How is equal weight treated?** As a benchmark judged by the same drawdown test. For a Balanced user, 1/N fell 20.6% at its worst, beyond their 15% limit, so for that profile it is not a safe default. When 1/N passes and beats us, the app says the optimizer does not earn its keep. Honesty either way.
9. **Where does the data come from?** Yahoo Finance daily adjusted closes for 11 EUR listed UCITS funds, retrieved live and cached; a frozen snapshot ships in the repo as fallback and as the deterministic verification input.
10. **How do you handle missing data?** Per universe common window; gaps up to 3 trading days forward filled (exchange holidays); longer gaps dropped, never invented. The app displays the exact counts for the active universe.
11. **How do you know your numbers are right?** `verify.py` recomputes CAGR, volatility and worst fall from raw prices with fully independent code and requires agreement to 4 decimals. During development it caught a real windowing bug, which is exactly why it exists.
12. **What does the projection actually assume?** That future daily returns are drawn from the same distribution as the observed window, independently day to day. That keeps fat tails but loses volatility clustering, so long horizon tails are understated; and it cannot produce a crisis type the window never contained. Both stated in the app.
13. **Why does the projection warn about extrapolation?** When the user's horizon is longer than the data window, the simulation can only reshuffle those years. For the Experienced tier that would mean projecting a crypto bull run for 20 years, so the app tells the user to treat upper paths as "if the recent past repeats forever".
14. **What about costs and taxes?** Excluded, and disclosed. With ETF expense ratios around 0.1 to 0.4 percent and our advice of yearly rebalancing, the ranking of portfolios would barely move, but absolute returns would be modestly lower.
15. **How often should the user rebalance?** We backtested the recommended portfolio under five policies. Returns barely differ (8.3 to 8.5% per year) but never rebalancing drifted the mix past the user's loss limit (worst fall 15.5%). Yearly, or on a five point drift, is our advice: rebalancing is risk control, not extra return.
16. **Is the AI chat part of the recommendation?** No. It is grounded on the user's own results and constrained to educational answers. Without an API key it does not appear, and nothing else depends on it. The key lives in Streamlit secrets, never in the repository.
17. **How much of this did AI build?** Most of the code was written with Claude Code under our product direction; every accept or reject decision, the concept, the universes and the risk framing were ours. We trusted nothing until the independent verification script agreed to 4 decimals. Full disclosure is in the repo.
18. **Why EUR listed UCITS funds?** Our user is a European retail investor. UCITS funds are what they can actually buy, and quoting everything in EUR avoids mixing currency risk into the drawdown story.
19. **What is the Sharpe ratio of the recommendation?** It is computed for every candidate and shown on hover in the Evidence scatter. We do not select on it; the user's constraint is a loss limit. If asked for the number, open the scatter and hover the star.
20. **What would you build next?** A cash and money market tier so short horizons get an allocation instead of a warning; a rebalancing advisor from our appendix backtest; exportable MiFID style suitability reports per recommendation.

## Demo script (10 minutes)

1. One line of problem framing (slide 2), then straight into the live app as a Beginner: tap through honestly, land on results (2 min).
2. Read the verdict cards aloud: return, worst episode inside the limit, what 1/N would have done (2 min).
3. Open Fine tune, drag the limit down until nothing qualifies, show the straight talk message, drag back (1 min).
4. Projection screen: median, the 1 in 20 floor, the extrapolation logic (1 min).
5. Open Evidence: the scatter, the out of sample check, the skfolio second opinion, the pipeline counts (2 min).
6. Ask Sage one question live, for example why the portfolio holds gold (1 min).
7. Close on limitations and the verification story (1 min). Fallback captures live in `docs/fallback/` if the wifi dies.
