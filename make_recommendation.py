"""Regenerate data/recommended.json deterministically from the snapshot.

This is the write half of the verification pipeline; verify.py is the
independent read half (it imports nothing from src/). Run both together
so the committed evidence always matches the committed recommendation:

    python make_recommendation.py && python verify.py

Demo profile: Beginner universe (full 12-year window), Balanced band
(-15% tolerance), 40% concentration cap — the same defaults the app's
headline demo uses. Fixed sampling seed makes the output reproducible.
"""

import numpy as np

from src import data, metrics, portfolio

TOLERANCE = 0.15
MAX_WEIGHT = 0.40
UNIVERSE = data.TIERS["Beginner"]


def main() -> None:
    prices = data.load_snapshot(UNIVERSE)
    returns = metrics.daily_returns(prices)
    window = (str(prices.index.min().date()),
              str(prices.index.max().date()))

    weights = portfolio.sample_weights(len(UNIVERSE))
    table = portfolio.portfolio_table(returns, weights)
    weight_cols = [f"w_{t}" for t in UNIVERSE]
    table = table[table[weight_cols].max(axis=1) <= MAX_WEIGHT]

    rec = portfolio.recommend(table, TOLERANCE)
    assert rec["feasible"], "demo profile should always be feasible"
    portfolio.save_recommendation(rec["row"], UNIVERSE, window, TOLERANCE)

    w = np.array([rec["row"][c] for c in weight_cols])
    print(f"recommendation regenerated: window {window[0]} -> {window[1]}, "
          f"tolerance -{TOLERANCE:.0%}, cagr {rec['row']['cagr']:.4f}, "
          f"max_dd {rec['row']['max_drawdown']:.4f}, "
          f"weights {np.round(w, 4).tolist()}")


if __name__ == "__main__":
    main()
