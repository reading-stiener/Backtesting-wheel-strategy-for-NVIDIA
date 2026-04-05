"""
visualizations.py — Equity curves, drawdowns, and trade charts.
"""

import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from src.config import OUTPUT_DIR


def _ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def plot_equity_curves(
    wheel_daily: pd.DataFrame,
    bh_daily: pd.DataFrame,
    splits: list[dict],
):
    """Overlay equity curves for Wheel vs Buy-and-Hold with split dates marked."""
    _ensure_output_dir()

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(wheel_daily.index, wheel_daily["total_value"], label="Wheel Strategy", linewidth=1.2)
    ax.plot(bh_daily.index, bh_daily["total_value"], label="Buy & Hold", linewidth=1.2, alpha=0.8)

    for s in splits:
        ax.axvline(s["date"], color="gray", linestyle="--", alpha=0.5, linewidth=0.8)
        ax.text(s["date"], ax.get_ylim()[1] * 0.95, f"{s['ratio']}:1 split",
                fontsize=8, rotation=90, va="top", ha="right", color="gray")

    ax.set_title("Wheel Strategy vs Buy-and-Hold — NVDA (2020–2024)")
    ax.set_ylabel("Portfolio Value ($)")
    ax.set_xlabel("Date")
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    fig.autofmt_xdate()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "equity_curves.png"), dpi=150)
    plt.close(fig)
    print("[viz] Saved equity_curves.png")


def plot_drawdowns(
    wheel_daily: pd.DataFrame,
    bh_daily: pd.DataFrame,
):
    """Drawdown chart for both strategies."""
    _ensure_output_dir()

    fig, ax = plt.subplots(figsize=(14, 4))

    for label, df in [("Wheel", wheel_daily), ("B&H", bh_daily)]:
        values = df["total_value"]
        cummax = values.cummax()
        dd = (values - cummax) / cummax
        ax.fill_between(dd.index, dd.values, alpha=0.3, label=label)
        ax.plot(dd.index, dd.values, linewidth=0.8)

    ax.set_title("Drawdown — Wheel vs Buy-and-Hold")
    ax.set_ylabel("Drawdown")
    ax.set_xlabel("Date")
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    fig.autofmt_xdate()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "drawdowns.png"), dpi=150)
    plt.close(fig)
    print("[viz] Saved drawdowns.png")


def plot_trade_scatter(trade_log: list[dict]):
    """Scatter plot: date vs total cycle premium, colored by exit type."""
    _ensure_output_dir()
    if not trade_log:
        return

    df = pd.DataFrame(trade_log)

    color_map = {
        "PUT_EXPIRED": "green",
        "CALLED_AWAY": "blue",
        "OPEN_AT_END": "gray",
    }

    fig, ax = plt.subplots(figsize=(14, 5))
    for exit_type, color in color_map.items():
        subset = df[df["exit_type"] == exit_type]
        if not subset.empty:
            ax.scatter(
                subset["entry_date"], subset["total_premiums"],
                c=color, label=exit_type, alpha=0.6, s=30, edgecolors="none",
            )

    ax.set_title("Wheel Cycles — Total Premium Collected by Outcome")
    ax.set_ylabel("Premium ($)")
    ax.set_xlabel("Date")
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    fig.autofmt_xdate()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "trade_scatter.png"), dpi=150)
    plt.close(fig)
    print("[viz] Saved trade_scatter.png")


def plot_monthly_returns(wheel_daily: pd.DataFrame):
    """Monthly returns heatmap."""
    _ensure_output_dir()

    values = wheel_daily["total_value"]
    monthly = values.resample("ME").last().pct_change().dropna()

    # Reshape into year x month
    years = sorted(monthly.index.year.unique())
    months = range(1, 13)
    data = np.full((len(years), 12), np.nan)

    for i, year in enumerate(years):
        for j, month in enumerate(months):
            mask = (monthly.index.year == year) & (monthly.index.month == month)
            vals = monthly[mask]
            if not vals.empty:
                data[i, j] = vals.iloc[0]

    fig, ax = plt.subplots(figsize=(12, 4))
    im = ax.imshow(data, cmap="RdYlGn", aspect="auto", vmin=-0.3, vmax=0.3)

    ax.set_xticks(range(12))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    ax.set_yticks(range(len(years)))
    ax.set_yticklabels(years)

    # Annotate cells
    for i in range(len(years)):
        for j in range(12):
            val = data[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.1%}", ha="center", va="center",
                        fontsize=7, color="black" if abs(val) < 0.15 else "white")

    ax.set_title("Wheel Strategy — Monthly Returns")
    fig.colorbar(im, ax=ax, label="Return", shrink=0.8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "monthly_returns.png"), dpi=150)
    plt.close(fig)
    print("[viz] Saved monthly_returns.png")


def generate_all_plots(
    wheel_daily: pd.DataFrame,
    bh_daily: pd.DataFrame,
    trade_log: list[dict],
    splits: list[dict],
):
    """Generate all visualization plots."""
    print("\n[viz] Generating plots ...")
    plot_equity_curves(wheel_daily, bh_daily, splits)
    plot_drawdowns(wheel_daily, bh_daily)
    plot_trade_scatter(trade_log)
    plot_monthly_returns(wheel_daily)
    print("[viz] All plots saved to output/")
