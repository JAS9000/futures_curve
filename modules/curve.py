# curve.py
# Maths for a single futures curve at one point in time.
# Functions here take prices and return numbers. No internet, no plotting.


import math
import pandas as pd


# Classify the shape of the curve into a plain-English label.
# I check if EVERY step (P2-P1, P3-P2, ...) goes the same direction.
# If yes -> contango or backwardation. If not -> "mixed".
def classify(prices):
    if len(prices) < 2:
        return "n/a"
    # Look at every neighbouring pair
    all_rising = True
    all_falling = True
    for i in range(len(prices) - 1):
        if prices[i + 1] <= prices[i]:
            all_rising = False
        if prices[i + 1] >= prices[i]:
            all_falling = False
    if all_rising:
        return "contango"        # whole curve rises with delivery month
    if all_falling:
        return "backwardation"   # whole curve falls with delivery month
    return "mixed"               # some up, some down


# Pack all the headline numbers for one curve into a dict.
# Makes the app code shorter: just summary["front"] instead of separate calls.
def summarise_curve(prices):
    # Drop missing values and convert to a plain Python list
    prices = [float(p) for p in pd.Series(prices).dropna().values]
    if len(prices) < 2:
        # Not enough data - return NaNs so the UI shows "n/a"
        return {
            "front": prices[0] if len(prices) == 1 else float("nan"),
            "roll_yield_monthly": float("nan"),
            "classification": "n/a",
        }
    # Monthly holding return between the two nearest contracts = log(P1 / P2)
    monthly = math.log(prices[0] / prices[1])
    return {
        "front": prices[0],                   # headline price = nearest contract
        "roll_yield_monthly": monthly,        # per-month holding return
        "classification": classify(prices),
    }


# Friendly label for the metric card
def shape_label(classification):
    if classification == "backwardation":
        return "Falling (backwardation)"
    if classification == "contango":
        return "Rising (contango)"
    if classification == "mixed":
        return "Mixed shape"
    return "Not available"


# One-line plain-English meaning of the shape
def shape_meaning(classification):
    if classification == "backwardation":
        return "Near delivery costs more, so holding tends to pay over time."
    if classification == "contango":
        return "Later delivery costs more, so holding tends to cost over time."
    if classification == "mixed":
        return "Curve does not slope cleanly in one direction."
    return ""


# Build month labels like ["Jun 2026", "Jul 2026", ...] for the x-axis.
# Walk forward one month at a time from the as_of date.
def delivery_month_labels(as_of, n):
    # Start from the first day of the month AFTER as_of
    year = as_of.year
    month = as_of.month + 1
    if month > 12:
        month = 1
        year += 1

    labels = []
    for _ in range(n):
        # Use a Timestamp to format the label nicely
        labels.append(pd.Timestamp(year=year, month=month, day=1).strftime("%b %Y"))
        # Step one month forward
        month += 1
        if month > 12:
            month = 1
            year += 1
    return labels
