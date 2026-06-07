# analytics.py
# Functions that work on the whole curve frame over time, plus the logic
# for the two research questions. The "research" wrappers used to live in
# a separate file but were so thin that I moved them here.


import math
import pandas as pd

import config


# Daily annualised holding return for every day in the history.
# Formula: ln(c1/c2) / dt, where c1 and c2 are the first two columns.
def roll_yield_series(curve_df):
    # The ratio of the two nearest contract prices, one value per row.
    ratio = curve_df["c1"] / curve_df["c2"]
    # Keep only rows where the ratio is a real positive number. This drops
    # missing prices and the very rare days when a listed oil price was zero
    # or negative, which would otherwise make the logarithm below crash.
    ratio = ratio.dropna()
    ratio = ratio[ratio > 0]
    # ln(c1/c2) for each remaining row
    log_ratio = ratio.apply(math.log)
    # Divide by dt = 1/12 year to get an annualised rate
    dt = config.MONTHS_BETWEEN_CONTRACTS / 12.0
    return (log_ratio / dt).rename("holding_return")


# Cumulative "carry index". Shows what an investor would have earned
# (or lost) purely from rolling the contract each month, ignoring the
# spot price move. Used in section 3 to separate price effect from
# carry effect.
def carry_index(curve_df):
    holding_returns = roll_yield_series(curve_df)
    # Turn the annualised rate into a per-day rate, then compound by summing
    # the daily log returns and taking exp() at the end.
    daily = holding_returns / config.TRADING_DAYS_PER_YEAR
    return daily.cumsum().apply(math.exp).rename("carry_index")


# Front-month price, rebased to start at 1.0 so it can be compared with
# the carry index on the same chart.
def normalised_front(curve_df):
    front = curve_df["c1"].dropna()
    if front.empty:
        return front
    return (front / front.iloc[0]).rename("front_norm")


# Forward simple return of the front-month over horizon_days trading days.
# Example: horizon_days = 63 gives the price change from today to ~3 months.
def forward_returns(front, horizon_days):
    # shift(-horizon_days) looks into the future
    return (front.shift(-horizon_days) / front - 1.0).rename("future_return")


# How often did the curve switch between rising and falling?
# Just counting daily flips would be misleading because the holding return
# can wobble around zero. So I count "spells" with a minimum length and
# return the number of switches between long spells.
def regime_statistics(curve_df, min_spell_days=10):
    holding_returns = roll_yield_series(curve_df)
    if holding_returns.empty:
        return {"pct_falling": float("nan"), "pct_rising": float("nan"),
                "n_regime_changes": 0, "n_days": 0}

    # 1 if falling that day, 0 if rising. Use a plain Python list so the
    # loop below is easy to follow.
    falling = [1 if r > 0 else 0 for r in holding_returns]
    pct_falling = sum(falling) / len(falling) * 100.0

    # Walk through the days and collect "spell lengths".
    # A spell is a stretch of consecutive days in the same regime.
    spell_lengths = []
    current_regime = falling[0]
    current_length = 1
    for i in range(1, len(falling)):
        if falling[i] == current_regime:
            current_length += 1
        else:
            # Regime changed - record the spell that just ended
            spell_lengths.append(current_length)
            current_regime = falling[i]
            current_length = 1
    spell_lengths.append(current_length)   # final spell

    # Count only spells long enough to be a "real" regime
    long_spells = [length for length in spell_lengths if length >= min_spell_days]
    # n_changes = n long spells - 1 (the first spell isn't a change FROM anything)
    n_changes = max(0, len(long_spells) - 1)

    return {
        "pct_falling": pct_falling,
        "pct_rising": 100.0 - pct_falling,
        "n_regime_changes": n_changes,
        "n_days": len(holding_returns),
    }


# Express weekly inventory as a percent deviation from its seasonal normal.
# Crude oil stocks swing a lot through the year (e.g. driving season), so a
# raw level says nothing about whether stocks are "high" or "low".
# Instead, I compare each week to the average level for the same week of
# the year across the years available.
def inventory_seasonal_deviation(inventory):
    inv = inventory.dropna()
    if inv.empty:
        return pd.Series(dtype=float)

    # Step 1: build a {week_of_year: average inventory} map by walking
    # through every observation and grouping by ISO week number.
    sum_by_week = {}
    count_by_week = {}
    for date, value in inv.items():
        week = date.isocalendar().week
        sum_by_week[week] = sum_by_week.get(week, 0.0) + value
        count_by_week[week] = count_by_week.get(week, 0) + 1
    normal_by_week = {w: sum_by_week[w] / count_by_week[w] for w in sum_by_week}

    # Step 2: for each observation, compute the deviation from the normal
    # for its week of the year, expressed as a percentage of normal.
    deviations = []
    for date, value in inv.items():
        normal = normal_by_week[date.isocalendar().week]
        deviations.append((value - normal) / normal * 100.0)
    return pd.Series(deviations, index=inv.index, name="inv_deviation")


# Helper: for a single weekly date, find the closest curve date within
# `tolerance_days` and return the matching holding return.
# Returns None if nothing is close enough.
def nearest_holding_return(week_date, curve_dates, holding_returns, tolerance_days=7):
    # Find the date in curve_dates closest to week_date
    best_diff = None
    best_pos = -1
    for i, curve_date in enumerate(curve_dates):
        diff = abs((curve_date - week_date).days)
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_pos = i
    # If even the closest is more than `tolerance_days` away, skip it
    if best_diff is None or best_diff > tolerance_days:
        return None
    return holding_returns.iloc[best_pos]


# Question 2 maths: sort each week into "low / normal / high" inventory and
# compare average holding return in each bucket. Theory of storage predicts:
# low-inventory bucket > high-inventory bucket.
def inventory_buckets(curve_df, inventory):
    # First, the percent-deviation series for inventory
    inventory_dev = inventory_seasonal_deviation(inventory)
    holding_returns = roll_yield_series(curve_df)
    if inventory_dev.empty or holding_returns.empty:
        return {"low_mean": float("nan"), "mid_mean": float("nan"),
                "high_mean": float("nan"),
                "low_n": 0, "mid_n": 0, "high_n": 0,
                "supports": False, "n": 0}

    # Clip the inventory series to the curve frame's date range so we
    # don't end up pairing 1980s inventory with 2019 prices.
    curve_start = holding_returns.index.min()
    curve_end = holding_returns.index.max()
    inventory_dev = inventory_dev.loc[(inventory_dev.index >= curve_start)
                                    & (inventory_dev.index <= curve_end)]
    if inventory_dev.empty:
        return {"low_mean": float("nan"), "mid_mean": float("nan"),
                "high_mean": float("nan"),
                "low_n": 0, "mid_n": 0, "high_n": 0,
                "supports": False, "n": 0}

    # Pair each weekly inventory observation with the nearest daily
    # holding return. A 7-day tolerance keeps things sensible.
    curve_dates_list = list(holding_returns.index)
    deviations = []
    returns = []
    for week_date, dev_value in inventory_dev.items():
        match = nearest_holding_return(week_date, curve_dates_list,
                                    holding_returns)
        if match is not None:
            deviations.append(dev_value)
            returns.append(match)

    if len(deviations) < 30:
        return {"low_mean": float("nan"), "mid_mean": float("nan"),
                "high_mean": float("nan"),
                "low_n": 0, "mid_n": 0, "high_n": 0,
                "supports": False, "n": len(deviations)}

    # Build a small DataFrame so the tercile cuts are easy
    sample = pd.DataFrame({"deviation": deviations, "return": returns})

    # Tercile cut points: 33rd and 66th percentile of inventory deviation
    low_cut = sample["deviation"].quantile(1 / 3)
    high_cut = sample["deviation"].quantile(2 / 3)

    low_bucket = sample.loc[sample["deviation"] <= low_cut, "return"]
    mid_bucket = sample.loc[(sample["deviation"] > low_cut)
                            & (sample["deviation"] < high_cut), "return"]
    high_bucket = sample.loc[sample["deviation"] >= high_cut, "return"]

    # Convert means from decimal (0.05) to percent (5.0) for nicer numbers
    low_mean = low_bucket.mean() * 100
    mid_mean = mid_bucket.mean() * 100
    high_mean = high_bucket.mean() * 100

    return {
        "low_mean": low_mean,
        "mid_mean": mid_mean,
        "high_mean": high_mean,
        "low_n": len(low_bucket),
        "mid_n": len(mid_bucket),
        "high_n": len(high_bucket),
        "supports": low_mean > high_mean,
        "n": len(sample),
    }


# Question 1 maths: average forward return after a falling-curve day vs
# a rising-curve day, at each of the three forecast horizons.
def horizon_comparison(curve_df):
    holding_returns = roll_yield_series(curve_df)
    rows = []
    for label, days in config.FORWARD_HORIZONS.items():
        future = forward_returns(curve_df["c1"], days)
        # Inner join on dates - drops rows where either side is NaN
        combined = pd.concat([holding_returns, future], axis=1).dropna()
        combined.columns = ["holding", "future"]
        if combined.empty:
            continue
        # Days the curve was falling have positive holding return
        falling_days = combined.loc[combined["holding"] > 0, "future"]
        rising_days = combined.loc[combined["holding"] <= 0, "future"]
        # Convert to percent
        falling_mean = falling_days.mean() * 100 if len(falling_days) else float("nan")
        rising_mean = rising_days.mean() * 100 if len(rising_days) else float("nan")
        rows.append({
            "horizon": label,
            "falling": falling_mean,
            "rising": rising_mean,
            "gap": falling_mean - rising_mean,
        })
    return pd.DataFrame(rows)


# Pull out the curve (c1..c4) on the trading day nearest a target date.
# Used in section 1 to show "today vs 1 year ago".
def nearest_curve(curve_df, target_date):
    if curve_df.empty:
        return None
    target = pd.Timestamp(target_date)
    # Loop through the dates and pick the one with the smallest difference
    best_diff = None
    best_pos = -1
    for i, curve_date in enumerate(curve_df.index):
        diff = abs((curve_date - target).days)
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_pos = i
    if best_pos < 0:
        return None
    row = curve_df.iloc[best_pos]
    columns = [c for c in ["c1", "c2", "c3", "c4"] if c in curve_df.columns]
    result = row[columns].dropna()
    result.name = curve_df.index[best_pos].date().isoformat()
    return result
