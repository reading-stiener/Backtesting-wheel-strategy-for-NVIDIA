# Wheel Strategy Backtest - Implementation Plan

## Context
Backtest the Wheel Strategy (selling cash-secured puts + covered calls) on NVDA from Jan 2020 to Dec 2024, comparing performance vs buy-and-hold. Real WRDS OptionMetrics data is available (5M rows of options with greeks, stock prices, 30-day zero curve). The existing code downloads from yfinance — needs full rework to use the WRDS data.

---

## Project Structure

```
main.py                     # Entry point
src/
  __init__.py               # Package init
  config.py                 # Reworked: parameters + raw CSV paths
  data_loader.py            # Rewritten: load WRDS CSVs, handle splits
  option_selector.py        # NEW: find best option by delta/DTE
  wheel_engine.py           # NEW: state machine (core logic)
  benchmark.py              # NEW: buy-and-hold benchmark
  analytics.py              # NEW: performance metrics
  visualizations.py         # NEW: equity curves, drawdowns, charts
```

Delete: `src/generate_sample_data.py` (synthetic data not needed)

---

## Phase 1: Data Layer

### `src/config.py` — Rework
- Keep: `START_DATE`, `END_DATE`, `TICKER`, `TARGET_DELTA=0.30`, `TARGET_DTE=30`, `DTE_TOLERANCE=5`, `DELTA_TOLERANCE=0.05`, `COMMISSION_PER_CONTRACT=0.65`, `SHARES_PER_CONTRACT=100`
- Add: `INITIAL_CAPITAL=100_000`, `OUTPUT_DIR`, raw CSV paths (`OPTION_GREEKS_FILE`, `STOCK_PRICE_FILE`, `ZERO_CURVE_FILE`)
- Remove: yfinance parquet paths, processed dir references

### `src/data_loader.py` — Full Rewrite
Three loaders + a master `load_all()`:

1. **`load_stock_prices()`** — Read `nvda_option_prices.csv`. Detect splits from `cfadj` changes (12→48 on 2021-07-20 = 4:1 split, 48→480 on 2024-06-10 = 10:1 split). Return stock DataFrame + splits list.

2. **`load_option_chain()`** — Read `nvda_option_prices_greeks.csv` (5M rows). Convert `strike_price / 1000` to actual dollars. Compute `dte = (exdate - date).days` and `mid_price = (bid + offer) / 2`. Drop rows with null delta or zero bid/offer. Use dtype optimization for memory (~200MB).

3. **`load_zero_curve()`** — Read `zero_curve.csv`. Convert rate from % to decimal. Forward-fill gaps. Backfill early 2020 (data starts 2020-03-16) with `FALLBACK_RISK_FREE_RATE`.

---

## Phase 2: Option Selector (`src/option_selector.py`)

- **`build_option_index(options_df)`** — Pre-group by `(date, cp_flag)` for O(1) lookup per trading day.
- **`select_option(option_index, trade_date, cp_flag, target_delta, target_dte, ...)`** — Filter candidates by DTE ∈ [25,35], delta within tolerance of ±0.30. Pick closest delta match (break ties by DTE closest to 30). Return dict with strike, exdate, mid_price, delta, etc. or `None` if no match.

---

## Phase 3: Wheel Engine (`src/wheel_engine.py`) — Core

State machine with 4 states: `SELLING_CSP → WAITING_PUT_EXPIRY → SELLING_CC → WAITING_CALL_EXPIRY`

**Day-by-day loop:**
1. **Check split** — If cfadj changed: `shares *= ratio`, `cost_basis /= ratio`, `current_option.strike /= ratio`
2. **Check expiration** — If today ≥ option's exdate:
   - Put ITM (stock ≤ strike): **assigned** → buy 100 shares at strike, switch to CC phase
   - Put OTM: **expired worthless** → keep premium, sell new CSP
   - Call ITM (stock ≥ strike): **called away** → sell shares at strike, return to CSP phase
   - Call OTM: **expired worthless** → keep premium, sell new CC
3. **Sell new option** — If no active option:
   - CSP: verify `cash ≥ strike × 100` (cash-secured), collect premium - commission
   - CC: verify `shares ≥ 100`, collect premium - commission
4. **Record daily value** — `total_value = cash + shares × stock_close`

**Key design decisions:**
- One contract at a time (simple, $100K capital is sufficient)
- Hold to expiration (no early close)
- No option mark-to-market (total return is same; simplifies code)
- Trade log captures every option trade with entry/exit details and P&L

---

## Phase 4: Benchmark (`src/benchmark.py`)

**`run_buy_and_hold(stock_prices, splits, initial_capital)`**
- Day 1: buy `floor(capital / close)` shares, remainder stays as cash
- On split dates: `shares *= ratio`
- Daily value: `cash + shares × close`

---

## Phase 5: Analytics & Visualization

### `src/analytics.py`
- **`compute_metrics(daily_values)`** — CAGR, annualized vol, Sharpe ratio, max drawdown, Calmar ratio
- **`analyze_trades(trade_log)`** — Total trades, win rate, avg premium, assignments count, called-away count
- **`comparison_table()`** — Side-by-side Wheel vs Buy-and-Hold
- **`print_report()`** — Formatted console output

### `src/visualizations.py`
- Equity curves overlay (wheel vs B&H) with split dates marked
- Drawdown chart
- Trade scatter plot (date vs premium, colored by outcome)
- Monthly returns heatmap

---

## Phase 6: Integration (`main.py`)

Wire everything together:
1. Load data → 2. Build option index → 3. Run wheel → 4. Run B&H → 5. Compute metrics → 6. Print report → 7. Save CSVs to `output/` → 8. Generate plots

---

## Key Gotchas

| Issue | Resolution |
|-------|-----------|
| Strike prices ×1000 in WRDS | Divide by 1000 at load time |
| Stock splits (4:1 and 10:1) | Adjust shares, cost basis, and active option strike when cfadj changes |
| Option spanning a split | Adjust `current_option.strike /= ratio` when split detected |
| Zero curve missing Jan-Mar 2020 | Backfill with `FALLBACK_RISK_FREE_RATE` |
| 5M-row options file memory | dtype optimization + drop null-delta rows (~8%) |
| Put delta is negative in data | Filter puts by delta ∈ [-0.35, -0.25] |

---

## Verification

1. **Data loading smoke test:** Load all CSVs, print shapes, date ranges, split dates
2. **Option selector test:** Verify it finds reasonable options on 3-4 sample dates (early 2020, mid-2022, late 2024)
3. **Wheel engine short run:** Run on Jan-Mar 2020 only, inspect trade log manually
4. **Split handling:** Verify portfolio value is continuous across split dates
5. **Full backtest:** Run 2020-2024, check that total_value series is reasonable
6. **Benchmark sanity:** B&H final value should roughly match NVDA's ~30x gain over the period
7. **End-to-end:** `python main.py` produces console report + CSV outputs + charts in `output/`
