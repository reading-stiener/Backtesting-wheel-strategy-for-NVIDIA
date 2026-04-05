"""
main.py — Wheel Strategy Backtest Entry Point

Runs the full pipeline:
  1. Load WRDS data
  2. Build option index
  3. Run Wheel strategy
  4. Run Buy-and-Hold benchmark
  5. Compute metrics & print report
  6. Save CSVs to output/
  7. Generate plots
"""

import os
import pandas as pd

from src.config import OUTPUT_DIR
from src.data_loader import load_all
from src.option_selector import build_option_index
from src.wheel_engine import run_wheel
from src.benchmark import run_buy_and_hold
from src.analytics import compute_metrics, analyze_trades, print_report
from src.visualizations import generate_all_plots


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── 1. Load data ─────────────────────────────────────────────
    print("=" * 60)
    print("  LOADING DATA")
    print("=" * 60)
    data = load_all()
    stock_df = data["stock"]
    splits = data["splits"]
    options_df = data["options"]

    # ── 2. Build option index ────────────────────────────────────
    print("\n" + "=" * 60)
    print("  BUILDING OPTION INDEX")
    print("=" * 60)
    option_index = build_option_index(options_df)

    # ── 3. Run Wheel strategy ────────────────────────────────────
    print("\n" + "=" * 60)
    print("  RUNNING WHEEL STRATEGY")
    print("=" * 60)
    wheel_daily, trade_log, skip_stats = run_wheel(stock_df, splits, option_index)

    # ── 4. Run Buy-and-Hold ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("  RUNNING BUY-AND-HOLD BENCHMARK")
    print("=" * 60)
    bh_daily = run_buy_and_hold(stock_df, splits)

    # ── 5. Compute metrics & print report ────────────────────────
    wheel_metrics = compute_metrics(wheel_daily, label="Wheel Strategy")
    bh_metrics = compute_metrics(bh_daily, label="Buy & Hold")
    trade_stats = analyze_trades(trade_log)
    print_report(wheel_metrics, bh_metrics, trade_stats)

    # ── 6. Save CSVs ────────────────────────────────────────────
    wheel_daily.to_csv(os.path.join(OUTPUT_DIR, "wheel_daily.csv"))
    bh_daily.to_csv(os.path.join(OUTPUT_DIR, "bh_daily.csv"))
    pd.DataFrame(trade_log).to_csv(os.path.join(OUTPUT_DIR, "trade_log.csv"), index=False)

    comparison = pd.DataFrame([wheel_metrics, bh_metrics])
    comparison.to_csv(os.path.join(OUTPUT_DIR, "comparison.csv"), index=False)

    print(f"\n[output] CSVs saved to {OUTPUT_DIR}/")

    # ── 7. Generate plots ───────────────────────────────────────
    generate_all_plots(wheel_daily, bh_daily, trade_log, splits)

    print("\nDone!")


if __name__ == "__main__":
    main()
