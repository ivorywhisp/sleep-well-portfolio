"""Data pipeline: download, clean, and snapshot EUR-listed index ETF prices.

Provenance
----------
Provider: Yahoo Finance daily adjusted close via the `yfinance` library.
Instruments: eleven UCITS ETFs / ETCs listed on Euronext Amsterdam, Xetra
and Euronext Paris, all quoted in EUR, grouped into three knowledge tiers
(see TIERS). Retrieved on demand; `data/snapshot.csv` is a frozen copy
(see `refresh_snapshot`) used as an offline fallback and as the
deterministic input for independent verification.

Cleaning policy (documented for the "trustworthy pipeline" requirement)
-----------------------------------------------------------------------
1. Keep only dates from the first day ALL selected assets trade (common
   window), so every portfolio is compared on identical data.
2. Forward-fill gaps of up to 3 trading days. These gaps are national
   exchange holidays (e.g. German exchanges closed while Amsterdam trades);
   carrying the last price forward is the standard treatment.
3. Dates with longer gaps are DROPPED from the analysis window (the final
   `.dropna()` below) — prices are never invented to bridge them.
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
    "EQQQ.DE": "Nasdaq-100 — Invesco EQQQ",
    "IPRP.AS": "EU property — iShares European Property",
    "IUSN.DE": "World small caps — iShares MSCI World Small Cap",
    "BTCE.DE": "Bitcoin — BTCetc Physical Bitcoin ETC",
    "CL2.PA": "2x leveraged US equity — Amundi MSCI USA Lev 2x",
}

# MiFID-style appropriateness tiers: the knowledge/experience score decides
# which products the app may recommend AT ALL. Risk appetite never unlocks
# products — only knowledge does (and risk tolerance sets the target risk).
TIERS = {
    "Beginner": ["IWDA.AS", "EXSA.DE", "EMIM.AS", "IEAG.AS", "IBGL.AS",
                 "4GLD.DE"],
    "Intermediate": ["IWDA.AS", "EXSA.DE", "EMIM.AS", "IEAG.AS", "IBGL.AS",
                     "4GLD.DE", "EQQQ.DE", "IPRP.AS", "IUSN.DE"],
    "Experienced": ["IWDA.AS", "EXSA.DE", "EMIM.AS", "IEAG.AS", "IBGL.AS",
                    "4GLD.DE", "EQQQ.DE", "IPRP.AS", "IUSN.DE", "BTCE.DE",
                    "CL2.PA"],
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


def download_raw(tickers: list[str], years: int = 12) -> pd.DataFrame:
    """Download adjusted daily closes from Yahoo Finance, uncleaned."""
    import yfinance as yf  # imported here so snapshot mode works offline

    raw = yf.download(tickers, period=f"{years}y", interval="1d",
                      auto_adjust=True, progress=False)["Close"]
    if raw.empty:
        raise RuntimeError("Yahoo Finance returned no data")
    return raw[tickers]


def download_prices(tickers: list[str], years: int = 12) -> pd.DataFrame:
    """Download and clean prices for one selected universe.

    Cleaning happens per-universe, never across all known tickers: the
    common-window rule must only consider the assets actually in play
    (otherwise the youngest ticker would truncate everyone's history).
    """
    return clean_prices(download_raw(tickers, years))


def load_snapshot(tickers: list[str] | None = None) -> pd.DataFrame:
    """Load the frozen price snapshot shipped with the repository."""
    prices = pd.read_csv(SNAPSHOT_PATH, index_col=0, parse_dates=True)
    if tickers is not None:
        prices = clean_prices(prices[tickers])
    return prices


def load_prices(tickers: list[str],
                years: int = 12) -> tuple[pd.DataFrame, str]:
    """Return (prices, source). Tries a live download, falls back to snapshot.

    The source flag lets the app show a visible banner when running on
    frozen data instead of failing silently.
    """
    try:
        return download_prices(tickers, years), "live"
    except Exception:
        return load_snapshot(tickers), "snapshot"


def refresh_snapshot() -> None:
    """Re-download all tickers and freeze them to data/snapshot.csv.

    Stored RAW (full per-ticker history, NaN before listing) — cleaning is
    applied at load time for whichever universe is selected.
    """
    prices = download_raw(list(TICKERS), years=12)
    SNAPSHOT_PATH.parent.mkdir(exist_ok=True)
    prices.to_csv(SNAPSHOT_PATH)
    print(f"snapshot written: {SNAPSHOT_PATH} "
          f"({prices.index.min().date()} -> {prices.index.max().date()}, "
          f"{len(prices)} rows)")


if __name__ == "__main__":
    refresh_snapshot()
