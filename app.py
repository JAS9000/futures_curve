# app.py
# Streamlit interface for the Futures Curve Analyser.
# All the maths lives in the modules folder. This file just decides what
# to show on the page and in what order, using native Streamlit widgets.
# Run with: streamlit run app.py


import math
import os

import pandas as pd
import streamlit as st

import config
from modules import analytics
from modules import charts
from modules import curve as curve_math
from modules import data_eia
from modules import data_yf


# Has to be the first Streamlit call
st.set_page_config(page_title="Futures Curve Analyser", layout="wide")


# -------------------------------------------------------------------------- #
# Helper functions
# -------------------------------------------------------------------------- #


# Read the EIA key from .streamlit/secrets.toml or an environment variable
def get_api_key():
    # Try the secrets file first
    try:
        if "EIA_API_KEY" in st.secrets:
            return str(st.secrets["EIA_API_KEY"])
    except Exception:
        pass
    # Fall back to an environment variable
    return os.environ.get("EIA_API_KEY")


# Cache the curve data so it doesn't refetch on every slider move
@st.cache_data(show_spinner="Fetching crude oil futures from Yahoo Finance...")
def load_curve():
    # Fetch 10 years up front. The date picker can slice this down later.
    return data_yf.fetch_curve(years=10)


# Cache the inventory data the same way
@st.cache_data(show_spinner=False)
def load_inventory(api_key):
    return data_eia.fetch_inventory(api_key)


# Try the live curve, otherwise fall back to the synthetic data
def get_curve():
    try:
        return load_curve(), "Live market data"
    except Exception as e:
        st.warning(f"Could not fetch live data ({e}). Showing example data.")
        return data_yf.synthetic_curve(seed=7, level=65.0), "Example data"


# -------------------------------------------------------------------------- #
# Sidebar setup
# -------------------------------------------------------------------------- #

# Load the EIA key and test it once at startup
api_key = get_api_key()
key_ok, key_msg = data_eia.test_connection(api_key)

st.sidebar.header("Settings")

st.sidebar.subheader("EIA data status")
if key_ok:
    st.sidebar.success(key_msg)
else:
    st.sidebar.info(key_msg)

# Load the full curve frame (cached) so we know the available date range
full_curve, source = get_curve()
full_curve = full_curve.sort_index()
data_start = full_curve.index.min().date()
data_end = full_curve.index.max().date()

# Default to the most recent 5 years, which is a reasonable sample
default_start = max(data_start, (full_curve.index.max() - pd.DateOffset(years=5)).date())

st.sidebar.subheader("Analysis time frame")
# st.date_input with a tuple value gives a date-range picker
date_range = st.sidebar.date_input(
    "Pick the start and end date",
    value=(default_start, data_end),
    min_value=data_start,
    max_value=data_end,
)

# The widget returns a tuple of (start, end) when the user is finished picking,
# but during the in-between state it can return a single date. Handle both.
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    # User has only picked one date so far. Show everything up to that date.
    start_date = data_start
    end_date = date_range if not isinstance(date_range, tuple) else date_range[0]

st.sidebar.caption(f"Data available from {data_start} to {data_end}.")


# -------------------------------------------------------------------------- #
# Hero and intro
# -------------------------------------------------------------------------- #

st.title("Inside the Crude Oil Futures Curve")
st.divider()

# Paragraph 1: motivate the whole exercise.
# The hook is the surprising fact that nearly all oil "investors" never
# actually own any oil. Futures are how the investment industry takes oil
# exposure, so studying them is the only honest way to understand oil
# investing.
st.write(
    "**Almost everyone who invests in oil does so without ever owning a "
    "single barrel.** Storing physical crude is dangerous, expensive and "
    "tightly regulated, putting it out of reach for almost anyone outside "
    "the oil industry itself. Instead, financial exposure is taken through "
    "**futures contracts**, agreements to buy oil at a fixed price on a "
    "future date. Pension funds, ETFs, hedge funds and asset managers all "
    "use them, so understanding futures is the only honest way to see what "
    "an oil investment really delivers."
)

# Paragraph 2: what a futures curve is, and what rolling means.
st.write(
    "Each delivery month has its own futures price, and lined up by date "
    "these prices form a **curve**. Its shape shows whether supply today "
    "is tight (near delivery costs more, so the curve falls) or comfortable "
    "(later delivery costs more, so the curve rises), and it also drives "
    "returns. Because every contract expires, a long-term investor must "
    "keep selling the expiring contract and buying the next, which is "
    "called **rolling**. If the next contract is cheaper, rolling adds to "
    "the return. If it is more expensive, it subtracts. Over time this "
    "hidden gain or cost can matter more than the price of oil itself."
)

# Paragraph 3: a numbered list of the four steps in the report, so the
# structure is visible at a glance.
st.write("This program reads the live crude oil curve and works through it in four steps:")
st.markdown(
    """
    1. The shape of today's curve.
    2. How that shape has moved over time.
    3. How it adds to or subtracts from investor returns.
    4. Two research questions, testing influential claims from the finance literature.
    """
)

# Paragraph 4: the two research questions are the main destination, with
# each paper introduced as a bullet showing authors and what each did.
st.write(
    "The two research questions in section 4 are the main destination of "
    "the report. Sections 1 to 3 exist so the answers in section 4 carry "
    "real meaning. The questions test claims from:"
)
st.markdown(
    """
    * **Erb and Harvey (2006)**, *The Strategic and Tactical Value of
    Commodity Futures*. Shows that the spot price of a commodity carries
    little information about its long-run investment return, while the
    shape of its futures curve carries most of it.
    * **Gorton, Hayashi and Rouwenhorst (2013)**, *The Fundamentals of
    Commodity Futures Returns*. Connects physical inventory levels to the
    shape of futures curves across many commodities, providing the modern
    empirical backing for the older theory of storage.
    """
)


# -------------------------------------------------------------------------- #
# Slice the curve frame to the chosen date range
# -------------------------------------------------------------------------- #

# Clip to the user's chosen window
curve_df = full_curve.loc[(full_curve.index >= pd.Timestamp(start_date))
                        & (full_curve.index <= pd.Timestamp(end_date))]

if curve_df.empty:
    st.error("No data in the selected date range. Pick a wider range.")
    st.stop()

# List of curve columns that are actually present (should be c1..c4)
curve_cols = [c for c in ["c1", "c2", "c3", "c4"] if c in curve_df.columns]

# Pull out the most recent curve and compute the headline numbers
latest_prices = curve_df[curve_cols].iloc[-1]
latest_date = curve_df.index[-1]
summary = curve_math.summarise_curve(latest_prices)
delivery_labels = curve_math.delivery_month_labels(latest_date, len(curve_cols))

# Figure number counter to keep the titles in sync with the page order
figure_number = 0


# -------------------------------------------------------------------------- #
# Section 1: today's curve
# -------------------------------------------------------------------------- #

st.divider()
st.header("1. Today's curve")
st.caption(f"As of {latest_date.date().strftime('%d %B %Y')}. "
        f"Source: {source.lower()}.")

# Plain-English summary above the metric cards.
# Numbers that change with the data are wrapped in **bold** so the eye is
# drawn to them when re-reading.
shape = summary["classification"]
short_name = config.COMMODITY_SHORT.lower()
monthly_roll = summary["roll_yield_monthly"]
if shape == "contango":
    summary_text = (
        f"The {short_name} curve is currently **rising (contango)**. "
        f"Contracts for later delivery cost more than near delivery, which "
        f"usually points to comfortable supply. For an investor who holds "
        f"and **rolls** each month, this shape costs about "
        f"**{abs(monthly_roll)*100:.1f}%** per roll."
    )
elif shape == "backwardation":
    summary_text = (
        f"The {short_name} curve is currently **falling (backwardation)**. "
        f"Near delivery costs more than later delivery, which usually signals "
        f"tight supply. For an investor who holds and **rolls** each month, "
        f"this shape pays about **{monthly_roll*100:.1f}%** per roll."
    )
else:
    summary_text = (
        f"The {short_name} curve does not slope cleanly in one direction. "
        f"The signal from holding a position is **mixed**."
    )
st.write(summary_text)

# Three metric cards: price, monthly roll cost/gain, current shape
col1, col2, col3 = st.columns(3)

# Format helpers used only here, inline
def fmt_price(x):
    return "n/a" if math.isnan(x) else f"{x:,.2f}"
def fmt_pct(x):
    return "n/a" if math.isnan(x) else f"{x*100:+.1f}%"

col1.metric("Headline price (nearest contract)",
            fmt_price(summary["front"]),
            help=config.PRICE_UNIT)
col2.metric("Roll cost or gain, each month",
            fmt_pct(summary["roll_yield_monthly"]),
            help="What rolling the position costs or pays each time the "
                "contract is renewed.")
col3.metric("Current shape",
            curve_math.shape_label(summary["classification"]),
            help=curve_math.shape_meaning(summary["classification"]))

# Two charts side by side: today's curve, and the curve at past dates
chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    figure_number += 1
    st.plotly_chart(
        charts.curve_snapshot(figure_number, latest_prices,
                            summary["classification"], delivery_labels),
        width="stretch",
    )
with chart_col2:
    figure_number += 1
    # Collect snapshots at today, 1y, 2y and 3y ago
    snapshots = {}
    snapshot_offsets = [(0, "Today"),
                        (365, "One year ago"),
                        (730, "Two years ago"),
                        (1095, "Three years ago")]
    for days_back, label in snapshot_offsets:
        target = curve_df.index.max() - pd.Timedelta(days=days_back)
        snap = analytics.nearest_curve(curve_df[curve_cols], target)
        if snap is not None:
            snapshots[label] = snap
    st.plotly_chart(
        charts.curve_evolution(figure_number, snapshots),
        width="stretch",
    )

# Brief explanation of what the two figures show and what they mean
# for an investor. Use a bulleted list for the two figures so the reader
# can match each bullet to the chart on its side of the page.
st.write("The two figures show:")
st.markdown(
    """
    * **Left**: today's curve, one price per delivery month, ordered from
    nearest to furthest delivery. A line that slopes downward means
    **backwardation**, a line that slopes upward means **contango**.
    * **Right**: the curve as it looked today and one, two and three years
    ago, overlaid on the same axes. Both the level (price) and the tilt
    (shape) can be compared in one place.
    """
)
st.write(
    "For an investor, the headline price is only half the story. The middle "
    "metric card shows the return that comes purely from **rolling the "
    "contract each month**, independent of where the price goes. Section 2 "
    "follows that rolling return over time. Section 3 shows how much it "
    "adds up to."
)


# -------------------------------------------------------------------------- #
# Section 2: how the shape has moved
# -------------------------------------------------------------------------- #

st.divider()
st.header("2. How the shape has moved")
st.write(
    "The shape changes constantly, which is what makes it worth studying. "
    "The chart below shows the **holding return** over time."
)
st.markdown(
    """
    * **Above zero**: the curve was falling, and holding was paying.
    * **Below zero**: the curve was rising, and holding was costing.
    """
)

# Daily holding return for the whole window
holding_returns = analytics.roll_yield_series(curve_df)

figure_number += 1
st.plotly_chart(
    charts.holding_return_timeseries(figure_number, holding_returns),
    width="stretch",
)

# Quick descriptive statistic about regime switches.
# Use st.write so the text is at the normal body size, and wrap the changing
# numbers in **bold** so the eye is drawn to them.
regime = analytics.regime_statistics(curve_df)
pct_falling = regime["pct_falling"]
pct_rising = regime["pct_rising"]
n_changes = regime["n_regime_changes"]
st.write(
    f"Over the period shown, the curve was falling on about "
    f"**{pct_falling:.0f}%** of days and rising on the other "
    f"**{pct_rising:.0f}%**. It moved between the two states about "
    f"**{n_changes}** times, so the shape is far from permanent."
)


# -------------------------------------------------------------------------- #
# Section 3: how the curve adds to or subtracts from returns
# -------------------------------------------------------------------------- #

st.divider()
st.header("3. How the curve adds to or subtracts from returns")
st.write(
    "This is the part of an oil investment that the headline price never "
    "shows. Two investors watching the same headline price can end up with "
    "very different results, because rolling the contract each month quietly "
    "adds to or subtracts from what they hold. The chart separates the two "
    "effects:"
)
st.markdown(
    """
    * **Blue line**: the price alone, with no rolling effect.
    * **Gold line**: pure rolling, ignoring the price move.
    """
)

figure_number += 1
st.plotly_chart(
    charts.carry_vs_price(figure_number,
                        analytics.carry_index(curve_df),
                        analytics.normalised_front(curve_df)),
    width="stretch",
)
st.write(
    "Both lines start at **1.0**. When the gold line drifts above 1.0, "
    "rolling added to returns. When it drifts below, rolling subtracted "
    "from them. The gap between the two lines is the part of the result "
    "that the headline price never shows."
)


# -------------------------------------------------------------------------- #
# Section 4: two published ideas tested on this data
# -------------------------------------------------------------------------- #

st.divider()
st.header("4. Testing two ideas from finance research against the data")
st.write(
    "Sections 1 to 3 set up the tools. This section uses them. Each question "
    "below comes from a well-known paper in commodity finance. The paper's "
    "claim is stated in plain English, then translated into something "
    "concrete that can be tested on the data. Below each chart, a clear "
    "indicator shows whether the data over the chosen time window "
    "**supports** or **contradicts** the claim."
)


# ---- Question 1 ---------------------------------------------------------- #

st.subheader("Question 1: do falling curves predict stronger price returns?")

# Brief introduction to the paper before stating the claim
st.write(
    "**Erb and Harvey (2006)** published their paper **The Strategic and "
    "Tactical Value of Commodity Futures** in the Financial Analysts "
    "Journal. It is one of the most cited references on commodity futures "
    "investing. Their central finding was that the spot price of a "
    "commodity carries little information about its long run investment "
    "return. The shape of its futures curve carries most of it."
)

st.write(
    "**The claim.** The shape of the curve, not the headline price, drives "
    "the long run return of holding a commodity. Their example is heating "
    "oil, where the price rose by under 1% per year while holding the "
    "position added close to 5% per year, because energy curves are "
    "usually falling. **Translated to a test:** days with a falling curve "
    "should be followed by stronger price returns than days with a rising "
    "curve, on average."
)

# Run question 1: average forward return after falling vs rising days,
# at three different horizons (1m, 3m, 6m).
horizon_results = analytics.horizon_comparison(curve_df)

# A short time frame may not contain enough days to look months ahead, so
# there is nothing to compare. Show a friendly note instead of an error,
# and skip the chart and the result indicator for this question.
if horizon_results.empty:
    st.info(
        "The selected time frame is too short to test this question. "
        "Please pick a longer period (about a year or more works well)."
    )
else:
    # Bar chart of the result
    figure_number += 1
    st.plotly_chart(
        charts.horizon_comparison_chart(figure_number, horizon_results),
        width="stretch",
    )
    st.write(
        "**Green bars** show the average price return after days when the curve "
        "was falling. **Red bars** show the average return after days when it "
        "was rising. If the claim holds, the green bars should tend to be "
        "taller than the red ones."
    )

    # CONFIRMED / NOT CONFIRMED result indicator goes AFTER the chart.
    # Count how many of the horizons go the direction the theory predicts
    # (falling > rising), then a single if-else picks the indicator.
    n_horizons = len(horizon_results)
    n_matches = 0
    for gap in horizon_results["gap"]:
        if gap > 0:
            n_matches += 1
    avg_gap = horizon_results["gap"].mean()

    if n_matches >= 2 and avg_gap > 0:
        st.success(
            f"**Result: CONFIRMED.** **{n_matches}** of **{n_horizons}** "
            f"horizons go the predicted direction, with an average gap of "
            f"**{avg_gap:+.1f}** percentage points."
        )
    else:
        st.error(
            f"**Result: NOT CONFIRMED.** Only **{n_matches}** of "
            f"**{n_horizons}** horizons go the predicted direction. Average "
            f"gap is **{avg_gap:+.1f}** percentage points across horizons."
        )


# ---- Question 2 ---------------------------------------------------------- #

st.subheader("Question 2: does low inventory tip the curve into backwardation?")

# Brief introduction to the literature before stating the claim
st.write(
    "The **theory of storage** is one of the oldest ideas in commodity "
    "markets, going back to Kaldor (1939) and Working (1949). It was "
    "formalised by **Fama and French (1987)** in their paper **Commodity "
    "Futures Prices: Some Evidence on Forecast Power, Premiums, and the "
    "Theory of Storage**. The modern empirical reference is **Gorton, "
    "Hayashi and Rouwenhorst (2013)**, **The Fundamentals of Commodity "
    "Futures Returns**, which linked physical inventory levels to the "
    "shape of futures curves across many commodities."
)

st.write(
    "**The claim.** When stockpiles run low, the value of having the "
    "commodity on hand right now rises. That pushes the near price above "
    "later prices and tips the curve into a **falling** shape. When "
    "stockpiles are plentiful, the curve should **rise** instead. "
    "**Translated to a test:** weeks of unusually low inventory should "
    "have a falling curve more often, and weeks of unusually high "
    "inventory should have a rising curve more often."
)

# Try to fetch inventory data. If the EIA isn't reachable, skip the question.
inventory_series = None
if key_ok:
    inventory_series = load_inventory(api_key)

if inventory_series is None or len(inventory_series) == 0:
    st.write(
        "Inventory data is not available (no EIA key, or the EIA could not "
        "be reached). Question 2 will be skipped. Add a free EIA key in "
        "the secrets file to enable it."
    )
else:
    q2 = analytics.inventory_buckets(curve_df, inventory_series)

    if q2["n"] < 30:
        st.write("Not enough overlapping inventory and price history to "
                "test the relationship.")
    else:
        # Bar chart first
        figure_number += 1
        st.plotly_chart(
            charts.inventory_buckets_chart(figure_number, q2),
            width="stretch",
        )
        st.write(
            "Each week of history is sorted into one of three buckets by "
            "how unusual the inventory was for that time of year."
        )
        st.markdown(
            """
            * **Low**: inventory well below normal for that week of the year.
            * **Normal**: inventory near the seasonal average.
            * **High**: inventory well above normal for that week of the year.
            """
        )
        st.write(
            '"Normal" is the average level for the same week of the year '
            "across all years in the EIA series. If the theory holds, the "
            "**Low** bar should be higher than the **High** bar."
        )

        # CONFIRMED / NOT CONFIRMED result indicator goes AFTER the chart
        if q2["supports"]:
            st.success(
                f"**Result: CONFIRMED.** Across **{q2['n']}** weeks, "
                f"low-inventory weeks had an average holding return of "
                f"**{q2['low_mean']:+.1f}%** per year, vs "
                f"**{q2['high_mean']:+.1f}%** for high-inventory weeks. "
                f"Gap of **{q2['low_mean'] - q2['high_mean']:+.1f}** "
                f"percentage points runs in the direction the theory predicts."
            )
        else:
            st.error(
                f"**Result: NOT CONFIRMED.** Across **{q2['n']}** weeks, "
                f"low-inventory weeks had an average holding return of "
                f"**{q2['low_mean']:+.1f}%** per year, vs "
                f"**{q2['high_mean']:+.1f}%** for high-inventory weeks. "
                f"The expected pattern is weak or reversed in this window."
            )
