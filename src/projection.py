"""Wealth projection by bootstrap simulation.

We resample the recommended portfolio's OWN historical daily returns
(with replacement) to build thousands of alternative futures. Compared to
assuming normal returns, the bootstrap keeps the fat tails and crash days
that actually occurred in the sample — at the cost of assuming the future
draws from the same distribution as the past (disclosed as a limitation).
"""

import numpy as np
import pandas as pd

TRADING_DAYS = 252
N_PATHS = 2_000
SEED = 7
PERCENTILES = [5, 25, 50, 75, 95]


def simulate(port_returns: pd.Series, amount: float,
             years: int) -> pd.DataFrame:
    """Percentile wealth paths for `amount` invested over `years`.

    Returns a DataFrame indexed by year-fraction with one column per
    percentile (p5 … p95), sampled monthly for lightweight plotting.
    """
    rng = np.random.default_rng(SEED)
    n_days = years * TRADING_DAYS
    draws = rng.choice(port_returns.to_numpy(), size=(n_days, N_PATHS),
                       replace=True)
    wealth = amount * np.cumprod(1 + draws, axis=0)

    # monthly sampling keeps the chart payload small (~12 points/year)
    idx = np.arange(0, n_days, 21)
    pct = np.percentile(wealth[idx], PERCENTILES, axis=1).T
    out = pd.DataFrame(pct, columns=[f"p{p}" for p in PERCENTILES])
    out.index = (idx + 1) / TRADING_DAYS
    out.index.name = "years"
    return out
