"""Second opinion from a convex optimizer (skfolio, seen in class).

Our recommendation comes from transparent random sampling. skfolio's
MeanRisk solves the same problem exactly — maximize return subject to a
maximum-drawdown cap and the per-fund concentration limit — via convex
optimization. Agreement between the two is evidence the sampled answer
is near-optimal; divergence shows the optimizer exploiting corner
solutions (piling the few best-performing assets at their caps), which
is precisely why the app displays the sampled landscape and keeps the
optimizer as a cross-check.

Note: skfolio's drawdown constraint is defined on non-compounded wealth
(that is what keeps the problem convex); we report its portfolio with
our own compounded metrics for an apples-to-apples comparison.
"""

import numpy as np
import pandas as pd
from skfolio.optimization import MeanRisk, ObjectiveFunction


def second_opinion(returns: pd.DataFrame, tolerance: float,
                   max_weight: float) -> np.ndarray:
    """Optimal weights for max return s.t. worst drawdown <= tolerance."""
    model = MeanRisk(
        objective_function=ObjectiveFunction.MAXIMIZE_RETURN,
        max_max_drawdown=tolerance,
        min_weights=0.0, max_weights=max_weight,
    )
    model.fit(returns)
    return np.asarray(model.weights_)
