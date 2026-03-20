"""
Central configuration for the Wheel Strategy back-test.
"""

import os

# ── Time Period ──────────────────────────────────────────────────────────────
START_DATE = "2020-01-02"
END_DATE = "2024-12-31"

# ── Underlying ───────────────────────────────────────────────────────────────
TICKER = "NVDA"

# ── Strategy Parameters ──────────────────────────────────────────────────────
INITIAL_CAPITAL = 100_000
TARGET_DELTA = 0.30
TARGET_DTE = 30
DTE_TOLERANCE = 5
DELTA_TOLERANCE = 0.05
COMMISSION_PER_CONTRACT = 0.65
SHARES_PER_CONTRACT = 100

# ── Risk-Free Rate (fallback for early 2020 when zero curve is missing) ─────
FALLBACK_RISK_FREE_RATE = 0.015  # ~1.5% in early 2020

# ── Data Paths ───────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

OPTION_GREEKS_FILE = os.path.join(RAW_DIR, "nvda_option_prices_greeks.csv")
STOCK_PRICE_FILE = os.path.join(RAW_DIR, "nvda_option_prices.csv")
ZERO_CURVE_FILE = os.path.join(RAW_DIR, "zero_curve.csv")
