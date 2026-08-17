"""Independent verification of the app's recommended portfolio.

Deliberately imports NOTHING from src/ — the numbers are recomputed from
the frozen price snapshot with separate, minimal pandas code. If this
script and the app agree to 4 decimal places, a bug would have to exist
identically in two independent implementations.

Run after generating a recommendation (data/recommended.json):

    python verify.py

Writes verification_evidence.txt with the comparison.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
TRADING_DAYS = 252
TOLERANCE = 1e-4  # agreement required to 4 decimal places


def main() -> int:
    rec = json.loads((ROOT / "data" / "recommended.json").read_text())
    tickers, weights = rec["tickers"], np.array(rec["weights"])

    # Independent pipeline: read the same frozen snapshot, re-apply the
    # documented cleaning policy from scratch.
    prices = pd.read_csv(ROOT / "data" / "snapshot.csv",
                         index_col=0, parse_dates=True)[tickers]
    prices = prices.loc[prices.apply(lambda c: c.first_valid_index()).max():]
    prices = prices.ffill(limit=3).dropna()
    start, end = rec["window"]
    prices = prices.loc[start:end]

    # Portfolio daily returns at constant weights, then the two claims.
    rets = prices.pct_change().dropna()
    port = rets.values @ weights
    wealth = np.cumprod(1 + port)
    years = len(port) / TRADING_DAYS
    cagr = wealth[-1] ** (1 / years) - 1
    vol = port.std(ddof=1) * np.sqrt(TRADING_DAYS)
    peak = np.maximum.accumulate(wealth)
    max_dd = (wealth / peak - 1).min()

    recomputed = {"cagr": cagr, "vol": vol, "max_drawdown": max_dd}
    lines = ["Independent verification — Sleep-Well Portfolio",
             f"window: {start} -> {end}   assets: {', '.join(tickers)}",
             f"weights: {np.round(weights, 4).tolist()}", ""]
    ok = True
    for key, claimed in rec["claimed"].items():
        diff = abs(recomputed[key] - claimed)
        status = "MATCH" if diff < TOLERANCE else "MISMATCH"
        ok &= diff < TOLERANCE
        lines.append(f"{key:13s} app={claimed:+.6f}  "
                     f"recomputed={recomputed[key]:+.6f}  "
                     f"diff={diff:.2e}  {status}")
    lines.append("")
    lines.append("RESULT: " + ("all values confirmed to 4 decimals"
                               if ok else "DISAGREEMENT — investigate"))
    report = "\n".join(lines)
    print(report)
    (ROOT / "verification_evidence.txt").write_text(report + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
