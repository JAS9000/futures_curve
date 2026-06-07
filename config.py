# config.py
# Constants used across the project. Putting them here means I only have
# to change them in one place if I want to tweak something.


# EIA Open Data API base URL.
# Only used for the weekly inventory series in question 2.
# Live curve data comes from Yahoo Finance instead, since EIA stopped
# publishing NYMEX futures prices in April 2024.
EIA_API_BASE = "https://api.eia.gov/v2"


# Crude oil specifics.
# WTI = West Texas Intermediate, the U.S. benchmark crude.
# WCESTUS1 is the EIA series id for U.S. weekly crude oil ending stocks
# (in thousand barrels, released every Wednesday).
INVENTORY_ROUTE = "petroleum/stoc/wstk"
INVENTORY_SERIES = "WCESTUS1"
COMMODITY_SHORT = "Crude oil"
PRICE_UNIT = "US dollars per barrel"


# Standard exchange month codes used to build NYMEX contract names.
# Example: "CL" + "N" (= July) + "26" + ".NYM" = "CLN26.NYM"
#         = July 2026 crude oil contract on NYMEX
# These letter codes are an old futures market convention.
MONTH_CODES = {
    1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
    7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z",
}


# Curve maths.
# Contracts are 1 month apart (so c2 expires 1 month after c1).
# There are ~252 trading days per year (markets are closed weekends/holidays).
MONTHS_BETWEEN_CONTRACTS = 1
TRADING_DAYS_PER_YEAR = 252


# Forecast horizons for question 1, expressed in trading days.
# 21 trading days ≈ 1 month, 63 ≈ 3 months, 126 ≈ 6 months.
FORWARD_HORIZONS = {
    "One month ahead": 21,
    "Three months ahead": 63,
    "Six months ahead": 126,
}


# Local cache so the app starts fast after the first run.
# 12 hours is plenty for a weekly-updated series.
CACHE_DIR = "data"
CACHE_MAX_AGE_HOURS = 12


# Colours used by the charts (just strings passed to Plotly, no CSS).
GREEN = "#1F7A52"   # holding pays (falling curve)
RED = "#BD5A3C"     # holding costs (rising curve)
BLUE = "#3F6FB0"    # neutral series
GOLD = "#B07D2B"    # accent for the carry line
GREY = "#62707F"    # muted reference lines
