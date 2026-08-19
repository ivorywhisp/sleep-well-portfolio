"""Portfolio construction: sample the allocation space, filter by the
investor's drawdown tolerance, recommend the best survivor.

Why random sampling instead of an optimizer?
--------------------------------------------
A maximum-drawdown constraint on compounded wealth is non-convex, so
classical mean-variance solvers do not apply directly. Sampling ~10,000
random allocations is fully transparent (every candidate can be
inspected) and lets us show the user the whole feasible region instead
of a single black-box answer. Honest caveats: at 11 assets the sample is
sparse relative to the simplex, and picking the max-CAGR survivor is
in-sample selection on one realized history — both are disclosed in the
app, and a convex-optimizer cross-check (skfolio, src/crosscheck.py)
bounds how much return the sampling leaves on the table.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import metrics

N_PORTFOLIOS = 10_000
SEED = 42  # fixed so results are reproducible across runs and machines
CHUNK = 1_000  # keep wealth-curve matrices small (memory limit on free hosting)

RECOMMENDATION_PATH = (Path(__file__).resolve().parent.parent
                       / "data" / "recommended.json")


def sample_weights(n_assets: int, n_portfolios: int = N_PORTFOLIOS,
                   seed: int = SEED) -> np.ndarray:
    """Random long-only weights summing to 1 (uniform over the simplex)."""
    rng = np.random.default_rng(seed)
    return rng.dirichlet(np.ones(n_assets), size=n_portfolios)


def portfolio_table(returns: pd.DataFrame,
                    weights: np.ndarray) -> pd.DataFrame:
    """Metrics for each candidate allocation, computed in chunks.

    Returns a DataFrame with one row per portfolio: cagr, vol, sharpe,
    max_drawdown, plus the weight vector columns w_<ticker>.
    """
    daily = returns.values
    n_days = len(daily)
    years = n_days / metrics.TRADING_DAYS
    rows = []
    for start in range(0, len(weights), CHUNK):
        w_chunk = weights[start:start + CHUNK]
        port_daily = daily @ w_chunk.T                     # days x chunk
        wealth = np.cumprod(1 + port_daily, axis=0)        # days x chunk
        total_growth = wealth[-1]
        cagr = total_growth ** (1 / years) - 1
        # ddof=1 matches the pandas default used in metrics.py and verify.py
        daily_std = port_daily.std(axis=0, ddof=1)
        vol = daily_std * np.sqrt(metrics.TRADING_DAYS)
        mean = port_daily.mean(axis=0)
        sharpe = np.where(daily_std > 0,
                          mean / daily_std * np.sqrt(metrics.TRADING_DAYS),
                          0.0)
        running_peak = np.maximum.accumulate(wealth, axis=0)
        max_dd = (wealth / running_peak - 1).min(axis=0)
        rows.append(pd.DataFrame({
            "cagr": cagr, "vol": vol, "sharpe": sharpe, "max_drawdown": max_dd,
        }))
    table = pd.concat(rows, ignore_index=True)
    for i, ticker in enumerate(returns.columns):
        table[f"w_{ticker}"] = weights[:, i]
    return table


def equal_weight_row(returns: pd.DataFrame) -> pd.Series:
    """The mandatory benchmark: 1/N across the selected assets."""
    n = returns.shape[1]
    w = np.full(n, 1 / n)
    port = metrics.portfolio_returns(returns, w)
    return pd.Series({
        "cagr": metrics.cagr(port),
        "vol": metrics.annual_vol(port),
        "sharpe": metrics.sharpe(port),
        "max_drawdown": metrics.max_drawdown(port),
        "recovery_days": metrics.recovery_days(port),
    })


def recommend(table: pd.DataFrame, tolerance: float) -> dict:
    """Pick the highest-CAGR portfolio whose worst drawdown the investor
    could have sat through.

    tolerance is a positive fraction (0.15 = "I can stomach -15%").
    Returns a dict with keys: feasible (bool), row (pd.Series or None),
    n_feasible, closest_drawdown (only when nothing is feasible).
    """
    feasible = table[table["max_drawdown"] >= -tolerance]
    if feasible.empty:
        # Edge case: tolerance stricter than anything history offers.
        # Report the least-bad drawdown so the app can guide the user.
        return {"feasible": False, "row": None, "n_feasible": 0,
                "closest_drawdown": table["max_drawdown"].max()}
    best = feasible.loc[feasible["cagr"].idxmax()]
    return {"feasible": True, "row": best, "n_feasible": len(feasible),
            "closest_drawdown": None}


def save_recommendation(row: pd.Series, tickers: list[str],
                        window: tuple[str, str], tolerance: float) -> None:
    """Persist the recommended weights + claimed metrics as plain data.

    verify.py recomputes these numbers from the raw snapshot WITHOUT
    importing this package — the file is the only bridge between the two.
    """
    payload = {
        "tickers": tickers,
        "weights": [row[f"w_{t}"] for t in tickers],
        "claimed": {"cagr": row["cagr"], "vol": row["vol"],
                    "max_drawdown": row["max_drawdown"]},
        "window": list(window),
        "tolerance": tolerance,
    }
    RECOMMENDATION_PATH.parent.mkdir(exist_ok=True)
    RECOMMENDATION_PATH.write_text(json.dumps(payload, indent=2))
