"""Named historical stress windows for the crisis-replay view.

Dates mark the commonly cited start of the selloff to (approximate) trough
or, for 2022, the full calendar year of the joint stock-bond decline. All
windows fall inside our 2014+ data sample.
"""

import numpy as np
import pandas as pd

from . import metrics

STRESS_WINDOWS = {
    "China scare 2015-16": {
        "start": "2015-08-10", "end": "2016-02-11",
        "story": "Yuan devaluation and growth fears hit global equities.",
    },
    "Q4 2018 selloff": {
        "start": "2018-10-01", "end": "2018-12-24",
        "story": "Rate-hike fears; S&P 500 fell ~19% in under three months.",
    },
    "COVID crash 2020": {
        "start": "2020-02-19", "end": "2020-03-23",
        "story": "Fastest ~34% global equity drop on record — the moment "
                 "our investor sold at the bottom.",
    },
    "2022 inflation shock": {
        "start": "2022-01-01", "end": "2022-12-31",
        "story": "Stocks AND bonds fell together — the year diversification "
                 "seemed to fail.",
    },
}


def replay(returns: pd.DataFrame, weights: np.ndarray,
           window_key: str) -> pd.Series:
    """Wealth curve of a portfolio through one stress window, starting at 1.

    Shows what the investor would have watched happen to each euro
    invested the day the episode began.
    """
    spec = STRESS_WINDOWS[window_key]
    sliced = returns.loc[spec["start"]:spec["end"]]
    port = metrics.portfolio_returns(sliced, weights)
    return metrics.wealth_curve(port)
