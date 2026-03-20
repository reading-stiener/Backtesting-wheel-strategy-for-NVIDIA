"""
option_selector.py — Find the best option by delta/DTE for each trading day.
"""

import pandas as pd
import numpy as np

from src.config import TARGET_DELTA, TARGET_DTE, DTE_TOLERANCE, DELTA_TOLERANCE


def build_option_index(options_df: pd.DataFrame) -> dict:
    """
    Pre-group options by (date, cp_flag) for O(1) lookup per trading day.

    Returns:
        dict mapping (Timestamp, str) -> DataFrame slice
    """
    print("[index] Building option index by (date, cp_flag) ...")
    grouped = {}
    for (date, cp_flag), group in options_df.groupby(["date", "cp_flag"]):
        grouped[(date, cp_flag)] = group
    print(f"[index] {len(grouped):,} (date, cp_flag) groups built.")
    return grouped


def select_option(
    option_index: dict,
    trade_date: pd.Timestamp,
    cp_flag: str,
    target_delta: float = TARGET_DELTA,
    target_dte: int = TARGET_DTE,
    dte_tolerance: int = DTE_TOLERANCE,
    delta_tolerance: float = DELTA_TOLERANCE,
) -> dict | None:
    """
    Select the best option for a given date and type (P or C).

    For puts: delta is negative in data, so we filter by
        delta in [-target_delta - tol, -target_delta + tol]
    For calls: delta is positive, filter by
        delta in [target_delta - tol, target_delta + tol]

    Returns dict with strike, exdate, mid_price, delta, dte, impl_volatility
    or None if no suitable option found.
    """
    key = (trade_date, cp_flag)
    if key not in option_index:
        return None

    candidates = option_index[key]

    # Filter by DTE range
    dte_min = target_dte - dte_tolerance
    dte_max = target_dte + dte_tolerance
    candidates = candidates[(candidates["dte"] >= dte_min) & (candidates["dte"] <= dte_max)]

    if candidates.empty:
        return None

    # Filter by delta range
    if cp_flag == "P":
        # Put deltas are negative; target -0.30
        delta_center = -target_delta
        delta_min = delta_center - delta_tolerance
        delta_max = delta_center + delta_tolerance
    else:
        # Call deltas are positive; target +0.30
        delta_center = target_delta
        delta_min = delta_center - delta_tolerance
        delta_max = delta_center + delta_tolerance

    candidates = candidates[
        (candidates["delta"] >= delta_min) & (candidates["delta"] <= delta_max)
    ]

    if candidates.empty:
        return None

    # Score: primary = closest delta to target, secondary = closest DTE to target
    candidates = candidates.copy()
    candidates["delta_dist"] = (candidates["delta"] - delta_center).abs()
    candidates["dte_dist"] = (candidates["dte"] - target_dte).abs()
    candidates.sort_values(["delta_dist", "dte_dist"], inplace=True)

    best = candidates.iloc[0]
    return {
        "strike": float(best["strike_price"]),
        "exdate": best["exdate"],
        "mid_price": float(best["mid_price"]),
        "delta": float(best["delta"]),
        "dte": int(best["dte"]),
        "impl_volatility": float(best["impl_volatility"]) if pd.notna(best["impl_volatility"]) else None,
    }
