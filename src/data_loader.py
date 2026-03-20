"""
data_loader.py — Load WRDS OptionMetrics CSVs for the Wheel Strategy back-test.

Three loaders + a master load_all():
  1. load_stock_prices()  — daily OHLC + split detection from cfadj
  2. load_option_chain()  — 5M rows of options with greeks
  3. load_zero_curve()    — 30-day zero-coupon rate
"""

import pandas as pd

from src.config import (
    STOCK_PRICE_FILE, OPTION_GREEKS_FILE, ZERO_CURVE_FILE,
    START_DATE, END_DATE, FALLBACK_RISK_FREE_RATE,
)


def load_stock_prices() -> tuple[pd.DataFrame, list[dict]]:
    """
    Load NVDA daily stock prices from nvda_option_prices.csv.
    Detect splits from cfadj column changes.

    Returns:
        (stock_df, splits) where splits is a list of
        {'date': Timestamp, 'ratio': int, 'cfadj_before': float, 'cfadj_after': float}
    """
    print("[stock] Loading stock prices ...")
    df = pd.read_csv(
        STOCK_PRICE_FILE,
        parse_dates=["date"],
        dtype={"secid": "int32", "cfadj": "float64"},
    )
    df.sort_values("date", inplace=True)
    df.set_index("date", inplace=True)

    # Detect splits: cfadj changes between consecutive rows
    splits = []
    cfadj_vals = df["cfadj"].values
    for i in range(1, len(cfadj_vals)):
        if cfadj_vals[i] != cfadj_vals[i - 1] and cfadj_vals[i - 1] != 0:
            ratio = round(cfadj_vals[i] / cfadj_vals[i - 1])
            splits.append({
                "date": df.index[i],
                "ratio": ratio,
                "cfadj_before": cfadj_vals[i - 1],
                "cfadj_after": cfadj_vals[i],
            })

    for s in splits:
        print(f"  Split detected: {s['date'].date()} — {s['ratio']}:1 "
              f"(cfadj {s['cfadj_before']} → {s['cfadj_after']})")

    print(f"[stock] {len(df)} trading days loaded. "
          f"Range: {df.index[0].date()} to {df.index[-1].date()}")
    return df, splits


def load_option_chain() -> pd.DataFrame:
    """
    Load NVDA option chain from nvda_option_prices_greeks.csv (~5M rows).
    Applies: strike/1000, compute DTE, mid_price, drop nulls.
    """
    print("[options] Loading option chain (this may take a moment) ...")
    dtype_map = {
        "cp_flag": "category",
        "strike_price": "float32",
        "best_bid": "float32",
        "best_offer": "float32",
        "volume": "float32",
        "open_interest": "float32",
        "impl_volatility": "float32",
        "delta": "float32",
        "gamma": "float32",
        "vega": "float32",
        "theta": "float32",
    }
    cols = [
        "date", "exdate", "cp_flag", "strike_price", "best_bid", "best_offer",
        "volume", "open_interest", "impl_volatility", "delta", "gamma", "vega", "theta",
    ]
    df = pd.read_csv(
        OPTION_GREEKS_FILE,
        usecols=cols,
        dtype=dtype_map,
        parse_dates=["date", "exdate"],
    )

    initial_rows = len(df)

    # Convert strike from WRDS format (×1000) to actual dollars
    df["strike_price"] = df["strike_price"] / 1000.0

    # Compute DTE and mid price
    df["dte"] = (df["exdate"] - df["date"]).dt.days
    df["mid_price"] = (df["best_bid"] + df["best_offer"]) / 2.0

    # Drop rows with null delta or zero bid/offer (unusable for selection)
    mask = (
        df["delta"].notna()
        & (df["best_bid"] > 0)
        & (df["best_offer"] > 0)
    )
    df = df[mask].copy()

    dropped = initial_rows - len(df)
    print(f"[options] Loaded {len(df):,} rows (dropped {dropped:,} with null delta / zero bid-offer)")
    print(f"  Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"  Strike range: ${df['strike_price'].min():.2f} – ${df['strike_price'].max():.2f}")
    print(f"  DTE range: {df['dte'].min()} – {df['dte'].max()}")

    return df


def load_zero_curve() -> pd.DataFrame:
    """
    Load 30-day zero-coupon rate from zero_curve.csv.
    Convert rate from % to decimal. Forward-fill gaps.
    Backfill early 2020 with FALLBACK_RISK_FREE_RATE.
    """
    print("[zero] Loading zero curve ...")
    df = pd.read_csv(ZERO_CURVE_FILE, parse_dates=["date"])
    # Keep only 30-day rates (should already be filtered, but just in case)
    df = df[df["days"] == 30].copy()
    df["rate"] = df["rate"] / 100.0  # percent to decimal
    df.set_index("date", inplace=True)
    df = df[["rate"]].sort_index()

    # Reindex to full business-day range and fill gaps
    full_range = pd.bdate_range(start=START_DATE, end=END_DATE)
    df = df.reindex(full_range)
    df.index.name = "date"

    # Forward-fill, then backfill early 2020 with fallback
    df.ffill(inplace=True)
    df.fillna(FALLBACK_RISK_FREE_RATE, inplace=True)

    print(f"[zero] Rate range: {df['rate'].min():.4f} – {df['rate'].max():.4f}")
    print(f"  Date range: {df.index[0].date()} to {df.index[-1].date()}")
    return df


def load_all() -> dict:
    """
    Master loader. Returns dict with keys: 'stock', 'splits', 'options', 'zero_curve'.
    """
    stock_df, splits = load_stock_prices()
    options_df = load_option_chain()
    zero_curve = load_zero_curve()

    print(f"\n[loader] All data loaded successfully.")
    return {
        "stock": stock_df,
        "splits": splits,
        "options": options_df,
        "zero_curve": zero_curve,
    }
