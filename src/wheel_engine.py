"""
wheel_engine.py — Core Wheel Strategy state machine.

States:
  SELLING_CSP         — looking to sell a cash-secured put
  WAITING_PUT_EXPIRY  — holding a short put until expiration
  SELLING_CC          — looking to sell a covered call
  WAITING_CALL_EXPIRY — holding a short call until expiration
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
        trade_log: list of dicts with trade details
    """
    cash = initial_capital
    shares = 0
    cost_basis = 0.0  # per-share cost basis when assigned
    state = SELLING_CSP
    current_option = None  # dict with strike, exdate, mid_price, premium_collected, etc.

    # Build split lookup: date -> ratio
    split_lookup = {s["date"]: s["ratio"] for s in splits}

    trade_log = []
    daily_records = []

    trading_days = stock_df.index.tolist()

    for date in trading_days:
        close = stock_df.loc[date, "close"]

        # ── 1. Check for stock split ─────────────────────────────────
        if date in split_lookup:
            ratio = split_lookup[date]
            if shares > 0:
                shares *= ratio
                cost_basis /= ratio
            if current_option is not None:
                current_option["strike"] /= ratio
            print(f"  [{date.date()}] SPLIT {ratio}:1 — "
                  f"shares={shares}, cost_basis=${cost_basis:.2f}")

        # ── 2. Check expiration ──────────────────────────────────────
        if current_option is not None and date >= current_option["exdate"]:
            if state == WAITING_PUT_EXPIRY:
                if close <= current_option["strike"]:
                    # Put ITM — assigned: buy 100 shares at strike
                    assignment_cost = current_option["strike"] * SHARES_PER_CONTRACT
                    cash -= assignment_cost
                    shares += SHARES_PER_CONTRACT
                    cost_basis = current_option["strike"]
                    trade_log.append({
                        **_trade_entry(current_option, date),
                        "outcome": "ASSIGNED",
                        "pnl": current_option["premium_collected"] - (current_option["strike"] - close) * SHARES_PER_CONTRACT,
                    })
                    print(f"  [{date.date()}] PUT ASSIGNED @ ${current_option['strike']:.2f} "
                          f"(stock=${close:.2f})")
                    state = SELLING_CC
                else:
                    # Put OTM — expired worthless, keep premium
                    trade_log.append({
                        **_trade_entry(current_option, date),
                        "outcome": "EXPIRED_WORTHLESS",
                        "pnl": current_option["premium_collected"],
                    })
                    state = SELLING_CSP

                current_option = None

            elif state == WAITING_CALL_EXPIRY:
                if close >= current_option["strike"]:
                    # Call ITM — called away: sell shares at strike
                    proceeds = current_option["strike"] * SHARES_PER_CONTRACT
                    cash += proceeds
                    pnl = (current_option["strike"] - cost_basis) * SHARES_PER_CONTRACT + current_option["premium_collected"]
                    trade_log.append({
                        **_trade_entry(current_option, date),
                        "outcome": "CALLED_AWAY",
                        "pnl": pnl,
                    })
                    print(f"  [{date.date()}] CALL ASSIGNED — shares called away @ "
                          f"${current_option['strike']:.2f} (stock=${close:.2f})")
                    shares = 0
                    cost_basis = 0.0
                    state = SELLING_CSP
                else:
                    # Call OTM — expired worthless, keep premium + keep shares
                    trade_log.append({
                        **_trade_entry(current_option, date),
                        "outcome": "EXPIRED_WORTHLESS",
                        "pnl": current_option["premium_collected"],
                    })
                    state = SELLING_CC

                current_option = None

        # ── 3. Sell new option if none active ────────────────────────
        if current_option is None:
            if state == SELLING_CSP:
                opt = select_option(option_index, date, "P")
                if opt is not None:
                    required_cash = opt["strike"] * SHARES_PER_CONTRACT
                    if cash >= required_cash:
                        premium = opt["mid_price"] * SHARES_PER_CONTRACT - COMMISSION_PER_CONTRACT
                        cash += premium
                        current_option = {
                            **opt,
                            "type": "P",
                            "entry_date": date,
                            "premium_collected": premium,
                        }
                        state = WAITING_PUT_EXPIRY

            elif state == SELLING_CC:
                opt = select_option(option_index, date, "C")
                if opt is not None and shares >= SHARES_PER_CONTRACT:
                    premium = opt["mid_price"] * SHARES_PER_CONTRACT - COMMISSION_PER_CONTRACT
                    cash += premium
                    current_option = {
                        **opt,
                        "type": "C",
                        "entry_date": date,
                        "premium_collected": premium,
                    }
                    state = WAITING_CALL_EXPIRY

        # ── 4. Record daily portfolio value ──────────────────────────
        total_value = cash + shares * close
        daily_records.append({
            "date": date,
            "total_value": total_value,
            "cash": cash,
            "shares": shares,
            "stock_close": close,
            "state": state,
        })

    daily_df = pd.DataFrame(daily_records).set_index("date")
    print(f"\n[wheel] Backtest complete. {len(trade_log)} trades executed.")
    print(f"  Final value: ${daily_df['total_value'].iloc[-1]:,.2f}")
    print(f"  Final state: {state}, shares={shares}, cash=${cash:,.2f}")
    return daily_df, trade_log


def _trade_entry(option: dict, exit_date: pd.Timestamp) -> dict:
    """Build a trade log entry from an option dict."""
    return {
        "entry_date": option["entry_date"],
        "exit_date": exit_date,
        "type": option["type"],
        "strike": option["strike"],
        "exdate": option["exdate"],
        "delta": option["delta"],
        "dte": option["dte"],
        "mid_price": option["mid_price"],
        "premium_collected": option["premium_collected"],
    }
