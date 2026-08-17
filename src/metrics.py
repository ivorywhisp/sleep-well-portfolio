"""Return and risk metrics.

All functions take pandas objects indexed by trading day. We annualize with
252 trading days. The risk-free rate is assumed 0 for Sharpe (documented
simplification: EUR cash rates were near zero for most of the sample).
"""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple daily returns from adjusted close prices."""
    return prices.pct_change().dropna(how="all")


def portfolio_returns(returns: pd.DataFrame, weights: np.ndarray) -> pd.Series:
    """Daily returns of a portfolio held at constant weights.

    Constant weights model an investor who rebalances back to target;
    daily rebalancing is the limiting approximation of that policy.
    """
    return pd.Series(returns.values @ weights, index=returns.index)


def wealth_curve(port_returns: pd.Series, start_value: float = 1.0) -> pd.Series:
    """Growth of an initial investment, compounding daily returns."""
    return start_value * (1 + port_returns).cumprod()


def cagr(port_returns: pd.Series) -> float:
    """Compound annual growth rate over the full sample."""
    total_growth = (1 + port_returns).prod()
    years = len(port_returns) / TRADING_DAYS
    return total_growth ** (1 / years) - 1


def annual_vol(port_returns: pd.Series) -> float:
    """Annualized standard deviation of daily returns."""
    return port_returns.std() * np.sqrt(TRADING_DAYS)


def sharpe(port_returns: pd.Series) -> float:
    """Annualized Sharpe ratio with rf = 0 (see module docstring)."""
    vol = port_returns.std()
    if vol == 0:
        return 0.0
    return port_returns.mean() / vol * np.sqrt(TRADING_DAYS)


def max_drawdown(port_returns: pd.Series) -> float:
    """Worst peak-to-trough loss, as a negative fraction (e.g. -0.34).

    This is the metric our investor actually feels: the deepest fall from a
    previous high, which is what triggers panic selling.
    """
    wealth = wealth_curve(port_returns)
    running_peak = wealth.cummax()
    drawdown = wealth / running_peak - 1
    return drawdown.min()


def recovery_days(port_returns: pd.Series) -> int | None:
    """Trading days from the deepest trough back to the prior peak.

    Returns None if the portfolio has not yet recovered by sample end.
    """
    wealth = wealth_curve(port_returns)
    running_peak = wealth.cummax()
    drawdown = wealth / running_peak - 1
    trough_date = drawdown.idxmin()
    peak_value = running_peak.loc[trough_date]
    after = wealth.loc[trough_date:]
    recovered = after[after >= peak_value]
    if recovered.empty:
        return None
    return int(after.index.get_loc(recovered.index[0]))
