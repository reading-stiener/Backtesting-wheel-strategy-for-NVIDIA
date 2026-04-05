"""
analytics.py — Performance metrics and reporting.
"""

import numpy as np
import pandas as pd


def compute_metrics(daily_values: pd.DataFrame, label: str = "Strategy") -> dict:
    """
    Compute key performance metrics from a daily total_value series.

    Returns dict with: CAGR, annualized_vol, sharpe, max_drawdown, calmar, total_return
    """
    values = daily_values["total_value"]
    n_days = (values.index[-1] - values.index[0]).days
    n_years = n_days / 365.25

    total_return = values.iloc[-1] / values.iloc[0] - 1
    cagr = (values.iloc[-1] / values.iloc[0]) ** (1 / n_years) - 1

    # Daily returns
    daily_returns = values.pct_change().dropna()
    ann_vol = daily_returns.std() * np.sqrt(252)

    # Sharpe (assume rf ~ 0 for simplicity — conservative estimate)
    sharpe = cagr / ann_vol if ann_vol > 0 else 0.0

    # Max drawdown
    cummax = values.cummax()
    drawdown = (values - cummax) / cummax
    max_dd = drawdown.min()

    # Calmar ratio
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0.0

    return {
        "label": label,
        "initial_value": values.iloc[0],
        "final_value": values.iloc[-1],
        "total_return": total_return,
        "cagr": cagr,
        "annualized_vol": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "calmar": calmar,
        "n_years": n_years,
    }


def analyze_trades(trade_log: list[dict]) -> dict:
    """
    Compute statistics from the cycle-based trade log.
    Each entry is a full cycle (CSP → optional assignment → CCs → exit).
    """
    if not trade_log:
        return {"total_cycles": 0}

    df = pd.DataFrame(trade_log)

    total = len(df)
    wins = (df["pnl"] > 0).sum()

    all_legs = [leg for c in trade_log for leg in c["legs"]]
    legs_df = pd.DataFrame(all_legs) if all_legs else pd.DataFrame()
    put_legs = (legs_df["type"] == "P").sum() if len(legs_df) > 0 else 0
    call_legs = (legs_df["type"] == "C").sum() if len(legs_df) > 0 else 0
    assignments = (legs_df["outcome"] == "ASSIGNED").sum() if len(legs_df) > 0 else 0

    return {
        "total_cycles": total,
        "put_expired": (df["exit_type"] == "PUT_EXPIRED").sum(),
        "called_away": (df["exit_type"] == "CALLED_AWAY").sum(),
        "open_at_end": (df["exit_type"] == "OPEN_AT_END").sum(),
        "total_legs": len(all_legs),
        "put_legs": put_legs,
        "call_legs": call_legs,
        "assignments": assignments,
        "win_rate": wins / total if total > 0 else 0,
        "avg_premium": df["total_premiums"].mean(),
        "total_premium": df["total_premiums"].sum(),
        "avg_pnl": df["pnl"].mean(),
        "total_pnl": df["pnl"].sum(),
    }


def comparison_table(wheel_metrics: dict, bh_metrics: dict) -> pd.DataFrame:
    """
    Build a side-by-side comparison DataFrame.
    """
    keys = ["initial_value", "final_value", "total_return", "cagr",
            "annualized_vol", "sharpe", "max_drawdown", "calmar"]
    data = {
        "Metric": keys,
        "Wheel": [wheel_metrics[k] for k in keys],
        "Buy & Hold": [bh_metrics[k] for k in keys],
    }
    return pd.DataFrame(data)


def print_report(wheel_metrics: dict, bh_metrics: dict, trade_stats: dict):
    """
    Print a formatted console report.
    """
    print("\n" + "=" * 70)
    print("  WHEEL STRATEGY BACKTEST REPORT")
    print("=" * 70)

    print(f"\n{'Metric':<25} {'Wheel':>15} {'Buy & Hold':>15}")
    print("-" * 55)

    fmt_map = {
        "initial_value":  ("Initial Value",  "${:>13,.0f}", "${:>13,.0f}"),
        "final_value":    ("Final Value",    "${:>13,.0f}", "${:>13,.0f}"),
        "total_return":   ("Total Return",   "{:>13.1%}",   "{:>13.1%}"),
        "cagr":           ("CAGR",           "{:>13.1%}",   "{:>13.1%}"),
        "annualized_vol": ("Ann. Volatility","{:>13.1%}",   "{:>13.1%}"),
        "sharpe":         ("Sharpe Ratio",   "{:>13.2f}",   "{:>13.2f}"),
        "max_drawdown":   ("Max Drawdown",   "{:>13.1%}",   "{:>13.1%}"),
        "calmar":         ("Calmar Ratio",   "{:>13.2f}",   "{:>13.2f}"),
    }

    for key, (label, fmt_w, fmt_bh) in fmt_map.items():
        w_val = fmt_w.format(wheel_metrics[key])
        bh_val = fmt_bh.format(bh_metrics[key])
        print(f"{label:<25} {w_val:>15} {bh_val:>15}")

    print("\n" + "-" * 55)
    print("  CYCLE STATISTICS (Wheel)")
    print("-" * 55)
    print(f"  Total cycles:       {trade_stats['total_cycles']}")
    print(f"  Put expired (no assignment): {trade_stats.get('put_expired', 0)}")
    print(f"  Assigned → called away:      {trade_stats.get('called_away', 0)}")
    print(f"  Open at end:                 {trade_stats.get('open_at_end', 0)}")
    print(f"  Total option legs:  {trade_stats.get('total_legs', 0)}")
    print(f"    Put legs:         {trade_stats.get('put_legs', 0)}")
    print(f"    Call legs:        {trade_stats.get('call_legs', 0)}")
    print(f"  Win rate:           {trade_stats.get('win_rate', 0):.1%}")
    print(f"  Avg cycle premium:  ${trade_stats.get('avg_premium', 0):,.2f}")
    print(f"  Total premium:      ${trade_stats.get('total_premium', 0):,.2f}")
    print(f"  Avg cycle P&L:      ${trade_stats.get('avg_pnl', 0):,.2f}")
    print(f"  Total P&L:          ${trade_stats.get('total_pnl', 0):,.2f}")
    print("=" * 70)
