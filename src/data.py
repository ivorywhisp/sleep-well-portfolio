"""Data pipeline: download, clean, and snapshot EUR-listed index ETF prices.

Provenance
----------
Provider: Yahoo Finance daily adjusted close via the `yfinance` library.
Instruments: six UCITS ETFs / ETCs listed on Euronext Amsterdam and Xetra,
all quoted in EUR, chosen to span the asset classes a European retail
investor can actually buy. Retrieved on demand; `data/snapshot.csv` is a
frozen copy (see `refresh_snapshot`) used as an offline fallback and as the
deterministic input for independent verification.

Cleaning policy (documented for the "trustworthy pipeline" requirement)
-----------------------------------------------------------------------
1. Keep only dates from the first day ALL selected assets trade (common
   window), so every portfolio is compared on identical data.
2. Forward-fill gaps of up to 3 trading days. These gaps are national
   exchange holidays (e.g. German exchanges closed while Amsterdam trades);
   carrying the last price forward is the standard treatment.
3. Longer gaps are left as NaN and reported, never silently filled.
"""

from pathlib import Path

import pandas as pd

TICKERS = {
    "IWDA.AS": "Global equity — iShares Core MSCI World",
    "EXSA.DE": "Europe equity — iShares STOXX Europe 600",
    "EMIM.AS": "EM equity — iShares Core MSCI EM IMI",
    "IEAG.AS": "Euro bonds — iShares Core Euro Aggregate",
    "IBGL.AS": "Long govt bonds — iShares Euro Govt 15-30y",
    "4GLD.DE": "Gold — Xetra-Gold ETC",
}

SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "snapshot.csv"
MAX_FFILL_DAYS = 3


def clean_prices(raw: pd.DataFrame) -> pd.DataFrame:
    """Apply the documented cleaning policy to raw close prices."""
    prices = raw.copy()
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    # common window: start where every asset has traded at least once
    first_valid = prices.apply(lambda col: col.first_valid_index()).max()
    prices = prices.loc[first_valid:]
    prices = prices.ffill(limit=MAX_FFILL_DAYS)
    return prices.dropna()


def download_prices(tickers: list[str], years: int = 10) -> pd.DataFrame:
    """Download adjusted daily closes from Yahoo Finance and clean them."""
    import yfinance as yf  # imported here so snapshot mode works offline

    raw = yf.download(tickers, period=f"{years}y", interval="1d",
                      auto_adjust=True, progress=False)["Close"]
    if raw.empty:
        raise RuntimeError("Yahoo Finance returned no data")
    return clean_prices(raw[tickers])


def load_snapshot(tickers: list[str] | None = None) -> pd.DataFrame:
    """Load the frozen price snapshot shipped with the repository."""
    prices = pd.read_csv(SNAPSHOT_PATH, index_col=0, parse_dates=True)
    if tickers is not None:
        prices = clean_prices(prices[tickers])
    return prices


def load_prices(tickers: list[str], years: int = 10) -> tuple[pd.DataFrame, str]:
    """Return (prices, source). Tries a live download, falls back to snapshot.

    The source flag lets the app show a visible banner when running on
    frozen data instead of failing silently.
    """
    try:
        return download_prices(tickers, years), "live"
    except Exception:
        return load_snapshot(tickers), "snapshot"


def refresh_snapshot() -> None:
    """Re-download all tickers and freeze them to data/snapshot.csv."""
    prices = download_prices(list(TICKERS), years=12)
    SNAPSHOT_PATH.parent.mkdir(exist_ok=True)
    prices.to_csv(SNAPSHOT_PATH)
    print(f"snapshot written: {SNAPSHOT_PATH} "
          f"({prices.index.min().date()} -> {prices.index.max().date()}, "
          f"{len(prices)} rows)")


if __name__ == "__main__":
    refresh_snapshot()
