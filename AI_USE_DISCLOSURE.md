# AI-Use Disclosure — Team Lakers, Sage Invest

## Tools used

- **Claude Code (Anthropic, Claude Fable 5)** — used as an AI pair-programmer throughout: it wrote the majority of the application code, the verification script and the tests, working under the team's product direction (concept, universe, risk framing, UI decisions and all accept/reject calls were the team's). It also helped debug UI issues found by the team during manual testing.
- **OpenAI API (gpt-4o-mini / gpt-5-mini)** — powers the in-app "Ask Sage" chat only. It is grounded on the current user's profile and portfolio numbers and instructed to give educational, non-advisory answers. The API key is stored in Streamlit secrets, never in the repository.
- **yfinance / skfolio / streamlit / pandas / numpy / plotly** — standard libraries; skfolio (seen in class) is used as an independent optimization cross-check.

## How the work was verified

- **Independent recomputation:** `verify.py` recomputes the recommendation's CAGR, volatility and maximum drawdown from the raw price snapshot using separately written code with no imports from the app's modules, and requires agreement to 4 decimals (see `verification_evidence.txt`). This check caught a real windowing bug during development, which is exactly what it exists for.
- **End-to-end tests:** `test_wizard.py` runs the full assessment → results flow headlessly for two contrasting personas via Streamlit's AppTest.
- **Cross-check by a second method:** skfolio's convex `MeanRisk` optimizer solves the same constrained problem; its result is displayed next to ours in the Evidence panel.
- **Manual review:** the team walked every screen, every control and the deployed app, and reviewed the finance logic (scoring, tier gating, drawdown filtering, projection assumptions) against the course material.

## Known limitations of the AI-assisted work

- AI-generated code can look right while being subtly wrong; that is why every headline number has an independent, non-AI recomputation path and the team treats `verify.py` agreement as the acceptance bar.
- The in-app chat can produce imprecise phrasing; it is constrained by a system prompt (educational only, no advice, honest about limitations) and the app's conclusions never depend on it.
- The analytical limitations of the app itself (historical window, no costs/taxes, bootstrap assumptions) are listed in the README and inside the app's Evidence panel.
