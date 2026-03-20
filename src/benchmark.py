"""
benchmark.py — Buy-and-hold benchmark for comparison.
"""

import math
import pandas as pd

from src.config import INITIAL_CAPITAL


def run_buy_and_hold(
    stock_df: pd.DataFrame,
    splits: list[dict],
    initial_capital: float = INITIAL_CAPITAL,
) -> pd.DataFrame:
    """
    Simple buy-and-hold: buy max shares on day 1, hold through end.

    Returns DataFrame indexed by date with 'total_value' column.
    """
    split_lookup = {s["date"]: s["ratio"] for s in splits}

    first_close = stock_df.iloc[0]["close"]
    shares = math.floor(initial_capital / first_close)
    cash = initial_capital - shares * first_close

    print(f"[B&H] Day 1: bought {shares} shares @ ${first_close:.2f}, "
          f"remaining cash: ${cash:.2f}")

    records = []
    for date in stock_df.index:
        # Apply split
        if date in split_lookup:
            ratio = split_lookup[date]
            shares *= ratio
            print(f"  [{date.date()}] SPLIT {ratio}:1 — shares={shares}")

        close = stock_df.loc[date, "close"]
        total_value = cash + shares * close
        records.append({"date": date, "total_value": total_value})

    df = pd.DataFrame(records).set_index("date")
    print(f"[B&H] Final value: ${df['total_value'].iloc[-1]:,.2f}")
    return df
