# data_yf.py
# Pulls crude oil futures data from Yahoo Finance.
# Also contains the synthetic curve used as a fallback if Yahoo is down,
# since these two paths are really the same job ("get a curve from somewhere").
#
# Background: the EIA used to publish the futures price data, but they
# stopped after April 2024. Yahoo Finance still has every individual
# monthly contract under tickers like CLN26.NYM (= July 2026 crude oil).
#
# The approach is:
# 1. Build a list of monthly contracts that span the history we want
# 2. Download each contract's price history
# 3. For each historical trading day, line up the four contracts that
#    were still "future" on that date - those become c1, c2, c3, c4


import math
import random

import pandas as pd
import yfinance as yf

import config


# Build a single contract ticker name.
# Format: CL + month-code-letter + 2-digit-year + .NYM
# Example: July 2026 -> CL + "N" + "26" + ".NYM" = "CLN26.NYM"
def contract_symbol(year, month):
    letter = config.MONTH_CODES[month]
    two_digit_year = str(year)[-2:]
    return f"CL{letter}{two_digit_year}.NYM"


# Approximate the date a contract stops trading.
# Real NYMEX crude oil contracts stop trading around the 20th of the
# month BEFORE delivery. To be safe, I treat the contract as expired
# 11 days BEFORE the start of its delivery month - this is the safer
# direction to round (treat as expired a bit early).
def contract_expiry(year, month):
    delivery_start = pd.Timestamp(year=year, month=month, day=1)
    return delivery_start - pd.Timedelta(days=11)


# Walk forward n months from a start date, returning a list of (year, month).
def next_contract_months(start, n):
    months = []
    y = start.year
    m = start.month
    for _ in range(n):
        months.append((y, m))
        # Step one month forward, rolling over the year if needed
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


# Try to download the price history for one contract.
# Returns a pandas Series indexed by date, or None if the contract
# doesn't exist (Yahoo returns a 404 for delisted ones).
def download_one_contract(symbol, start_date):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start_date.date().isoformat(),
                            auto_adjust=False)
    except Exception:
        return None
    if hist is None or hist.empty:
        return None
    close = hist["Close"].dropna()
    if close.empty:
        return None
    # Drop timezone info so dates line up cleanly across contracts
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close


# Main function: build a historical curve DataFrame with columns c1..c4.
def fetch_curve(years=8):
    today = pd.Timestamp.today().normalize()
    history_start = today - pd.DateOffset(years=years)

    # We need contracts that were still "future" at every historical date,
    # so we start the contract roster a month before the history window
    # and go 12 months past today to cover the latest trading days too.
    roster_start = history_start - pd.DateOffset(months=1)
    n_contracts = years * 12 + 12
    months = next_contract_months(roster_start, n_contracts)

    # Download each contract. Some will be missing (delisted) - that's OK.
    contract_data = {}
    for (year, month) in months:
        symbol = contract_symbol(year, month)
        prices = download_one_contract(symbol, history_start)
        if prices is not None:
            contract_data[(year, month)] = prices

    if not contract_data:
        # Caller falls back to synthetic data
        raise RuntimeError("Could not fetch any crude oil contracts.")

    # Collect every trading date that showed up in any contract
    all_dates = set()
    for series in contract_data.values():
        for date in series.index:
            all_dates.add(date)
    all_dates = sorted(all_dates)

    # For each date, find the 4 contracts that haven't expired yet
    # and put their prices in c1..c4 (ordered nearest -> furthest delivery)
    rows = []
    for date in all_dates:
        # Build a list of (year, month, price) for contracts still active
        still_active = []
        for (year, month), series in contract_data.items():
            if contract_expiry(year, month) <= date:
                continue   # already expired
            if date not in series.index:
                continue   # no price on that date
            still_active.append((year, month, float(series.loc[date])))

        # Sort by delivery month so c1 is the nearest
        still_active.sort(key=lambda item: (item[0], item[1]))

        if len(still_active) < 2:
            continue   # need at least c1 and c2

        row = {"date": date}
        for i, (_, _, price) in enumerate(still_active[:4]):
            row[f"c{i+1}"] = price
        rows.append(row)

    if not rows:
        raise RuntimeError("Could not build a curve frame.")

    frame = pd.DataFrame(rows).set_index("date").sort_index()
    # Keep only dates where at least c1 and c2 are available
    return frame.dropna(subset=["c1", "c2"])


# ---- synthetic curve fallback -------------------------------------------- #
# Used only when Yahoo can't be reached. The data is labelled as fake
# in the UI so the user never thinks it's real prices.

def synthetic_curve(seed=7, years=6, level=70.0):
    # Use Python's random module with a fixed seed for reproducibility
    rng = random.Random(seed)

    # Build the business-day date index first, then let the data length follow
    # it. Some pandas versions return one row fewer when "today" lands on a
    # weekend, so we never assume an exact count: n_days is read back from the
    # index itself, which keeps the c1..c4 lists and the index the same length.
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=years * 252)
    n_days = len(dates)

    # Front price: mean-reverting random walk in log-space
    # Each day pulls a bit toward log(level), plus a random shock
    log_mean = math.log(level)
    pull_strength = 0.015      # how strongly the price reverts
    daily_noise = 0.02         # daily volatility
    front_prices = []
    x = log_mean
    for _ in range(n_days):
        # standard normal shock
        shock = rng.gauss(0, 1)
        x = x + pull_strength * (log_mean - x) + daily_noise * shock
        front_prices.append(math.exp(x))

    # Carry term that oscillates slowly between positive and negative,
    # so the synthetic curve flips between contango and backwardation.
    carry_values = []
    for i in range(n_days):
        # Sine wave over the whole period, plus a small random bump
        phase = (i / n_days) * (years * 2 * math.pi)
        wave = 0.010 * math.sin(phase)
        noise = rng.gauss(0, 0.003)
        carry_values.append(wave + noise)

    # Build c1..c4 from the front price and the monthly carry
    c1 = front_prices
    c2 = [c1[i] * math.exp(carry_values[i] * 1) for i in range(n_days)]
    c3 = [c1[i] * math.exp(carry_values[i] * 2) for i in range(n_days)]
    c4 = [c1[i] * math.exp(carry_values[i] * 3) for i in range(n_days)]

    return pd.DataFrame({"c1": c1, "c2": c2, "c3": c3, "c4": c4}, index=dates)
