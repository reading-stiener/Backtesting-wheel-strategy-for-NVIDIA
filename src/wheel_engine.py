"""
wheel_engine.py — Core Wheel Strategy state machine.

States:
  SELLING_CSP         — looking to sell a cash-secured put
  WAITING_PUT_EXPIRY  — holding a short put until expiration
  SELLING_CC          — looking to sell a covered call
  WAITING_CALL_EXPIRY — holding a short call until expiration

P&L accounting:
  A "trade" in the log is a full CYCLE, not a single option leg.
  - CSP expires worthless → cycle P&L = premium collected
  - CSP assigned → CC(s) sold → called away:
    cycle P&L = sum of all premiums + (exit_price - put_strike) * 100
"""

import pandas as pd

from src.config import (
    INITIAL_CAPITAL, COMMISSION_PER_CONTRACT, SHARES_PER_CONTRACT,
)
from src.option_selector import select_option


# States
SELLING_CSP = "SELLING_CSP"
WAITING_PUT_EXPIRY = "WAITING_PUT_EXPIRY"
SELLING_CC = "SELLING_CC"
WAITING_CALL_EXPIRY = "WAITING_CALL_EXPIRY"


def run_wheel(
    stock_df: pd.DataFrame,
    splits: list[dict],
    option_index: dict,
    initial_capital: float = INITIAL_CAPITAL,
) -> tuple[pd.DataFrame, list[dict]]:
    """
    Run the Wheel Strategy day-by-day.

    Returns:
        (daily_values_df, trade_log)
        daily_values_df: DataFrame indexed by date with 'total_value' column
        trade_log: list of cycle dicts with entry/exit details and P&L
    """
    cash = initial_capital
    shares = 0
    cost_basis = 0.0
    state = SELLING_CSP
    current_option = None

    # Cycle tracking: accumulates data across put + call legs
    cycle = None

    split_lookup = {s["date"]: s["ratio"] for s in splits}
    trade_log = []
    daily_records = []

    # Skip counters
    skipped_no_candidate = 0
    skipped_insufficient_cash = 0
    days_waiting = 0

    for date in stock_df.index:
        close = stock_df.loc[date, "close"]

        # ── 1. Check for stock split ─────────────────────────────────
        if date in split_lookup:
            ratio = split_lookup[date]
            if shares > 0:
                shares *= ratio
                cost_basis /= ratio
            if current_option is not None:
                current_option["strike"] /= ratio
            if cycle is not None:
                cycle["put_strike"] /= ratio
            print(f"  [{date.date()}] SPLIT {ratio}:1 — "
                  f"shares={shares}, cost_basis=${cost_basis:.2f}")

        # ── 2. Check expiration ──────────────────────────────────────
        if current_option is not None and date >= current_option["exdate"]:
            leg = _make_leg(current_option, date)

            if state == WAITING_PUT_EXPIRY:
                if close <= current_option["strike"]:
                    # Put ITM — assigned: buy 100 shares at strike
                    cash -= current_option["strike"] * SHARES_PER_CONTRACT
                    shares += SHARES_PER_CONTRACT
                    cost_basis = current_option["strike"]
                    leg["outcome"] = "ASSIGNED"
                    cycle["legs"].append(leg)
                    print(f"  [{date.date()}] PUT ASSIGNED @ ${current_option['strike']:.2f} "
                          f"(stock=${close:.2f})")
                    state = SELLING_CC
                else:
                    # Put OTM — expired worthless. Cycle complete.
                    leg["outcome"] = "EXPIRED_WORTHLESS"
                    cycle["legs"].append(leg)
                    cycle["exit_date"] = date
                    cycle["exit_type"] = "PUT_EXPIRED"
                    cycle["exit_price"] = None
                    cycle["pnl"] = cycle["total_premiums"]
                    trade_log.append(cycle)
                    cycle = None
                    state = SELLING_CSP

                current_option = None

            elif state == WAITING_CALL_EXPIRY:
                if close >= current_option["strike"]:
                    # Call ITM — called away: sell shares at strike
                    proceeds = current_option["strike"] * SHARES_PER_CONTRACT
                    cash += proceeds
                    leg["outcome"] = "CALLED_AWAY"
                    cycle["legs"].append(leg)
                    # Cycle complete: true round-trip P&L
                    cycle["exit_date"] = date
                    cycle["exit_type"] = "CALLED_AWAY"
                    cycle["exit_price"] = current_option["strike"]
                    cycle["pnl"] = (cycle["total_premiums"]
                                    + (current_option["strike"] - cycle["put_strike"])
                                    * SHARES_PER_CONTRACT)
                    trade_log.append(cycle)
                    cycle = None
                    print(f"  [{date.date()}] CALL ASSIGNED — shares called away @ "
                          f"${current_option['strike']:.2f} (stock=${close:.2f})")
                    shares = 0
                    cost_basis = 0.0
                    state = SELLING_CSP
                else:
                    # Call OTM — expired worthless, keep premium + keep shares
                    leg["outcome"] = "EXPIRED_WORTHLESS"
                    cycle["legs"].append(leg)
                    state = SELLING_CC

                current_option = None

        # ── 3. Sell new option if none active ────────────────────────
        if current_option is None:
            if state == SELLING_CSP:
                opt = select_option(option_index, date, "P")
                if opt is None:
                    skipped_no_candidate += 1
                elif cash < opt["strike"] * SHARES_PER_CONTRACT:
                    skipped_insufficient_cash += 1
                else:
                    premium = opt["mid_price"] * SHARES_PER_CONTRACT - COMMISSION_PER_CONTRACT
                    cash += premium
                    current_option = {
                        **opt,
                        "type": "P",
                        "entry_date": date,
                        "premium_collected": premium,
                    }
                    # Start a new cycle
                    cycle = {
                        "entry_date": date,
                        "put_strike": opt["strike"],
                        "total_premiums": premium,
                        "legs": [],
                    }
                    state = WAITING_PUT_EXPIRY

            elif state == SELLING_CC:
                opt = select_option(option_index, date, "C")
                if opt is None:
                    skipped_no_candidate += 1
                elif shares < SHARES_PER_CONTRACT:
                    pass
                else:
                    premium = opt["mid_price"] * SHARES_PER_CONTRACT - COMMISSION_PER_CONTRACT
                    cash += premium
                    current_option = {
                        **opt,
                        "type": "C",
                        "entry_date": date,
                        "premium_collected": premium,
                    }
                    cycle["total_premiums"] += premium
                    state = WAITING_CALL_EXPIRY
        else:
            days_waiting += 1

        # ── 4. Record daily portfolio value ──────────────────────────
        daily_records.append({
            "date": date,
            "total_value": cash + shares * close,
            "cash": cash,
            "shares": shares,
            "stock_close": close,
            "state": state,
        })

    # Close any open cycle at market value
    if cycle is not None:
        last_close = stock_df.iloc[-1]["close"]
        cycle["exit_date"] = stock_df.index[-1]
        cycle["exit_type"] = "OPEN_AT_END"
        if shares > 0:
            cycle["exit_price"] = last_close
            cycle["pnl"] = (cycle["total_premiums"]
                            + (last_close - cycle["put_strike"]) * SHARES_PER_CONTRACT)
        else:
            cycle["exit_price"] = None
            cycle["pnl"] = cycle["total_premiums"]
        trade_log.append(cycle)

    daily_df = pd.DataFrame(daily_records).set_index("date")
    skip_stats = {
        "skipped_no_candidate": skipped_no_candidate,
        "skipped_insufficient_cash": skipped_insufficient_cash,
        "days_waiting": days_waiting,
    }
    total_legs = sum(len(c["legs"]) for c in trade_log)
    print(f"\n[wheel] Backtest complete. {len(trade_log)} cycles, {total_legs} option legs.")
    print(f"  Final value: ${daily_df['total_value'].iloc[-1]:,.2f}")
    print(f"  Final state: {state}, shares={shares}, cash=${cash:,.2f}")
    print(f"\n  Day breakdown ({len(daily_records)} trading days):")
    print(f"    Holding active option:  {days_waiting}")
    print(f"    Skipped (no candidate): {skipped_no_candidate}")
    print(f"    Skipped (low cash):     {skipped_insufficient_cash}")
    print(f"    New option sold:        {total_legs}")
    return daily_df, trade_log, skip_stats


def _make_leg(option: dict, exit_date: pd.Timestamp) -> dict:
    """Build a leg record from an active option dict."""
    return {
        "type": option["type"],
        "entry_date": option["entry_date"],
        "exit_date": exit_date,
        "strike": option["strike"],
        "exdate": option["exdate"],
        "delta": option["delta"],
        "dte": option["dte"],
        "mid_price": option["mid_price"],
        "premium": option["premium_collected"],
    }
