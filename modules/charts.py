# charts.py
# All the Plotly figures used in the app. Each chart gets a title like
# "Figure N. Title" so they're easy to refer to in the surrounding text.


import plotly.graph_objects as go

import config


# Apply the same layout to every figure - keeps the look consistent
def style(fig, number, title, ytitle=None, xtitle=None, legend=False, height=380):
    fig.update_layout(
        title=f"Figure {number}. {title}",
        title_x=0,
        title_font_size=15,
        height=height,
        margin=dict(l=60, r=20, t=60, b=70),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=legend,
        legend=dict(orientation="h", yanchor="top", y=-0.18,
                    xanchor="center", x=0.5),
    )
    fig.update_xaxes(title=xtitle, gridcolor="#EEEAE1", zeroline=False)
    fig.update_yaxes(title=ytitle, gridcolor="#EEEAE1", zeroline=False)
    return fig


# Pick the line colour for the snapshot chart depending on the shape
def shape_colour(classification):
    if classification == "backwardation":
        return config.GREEN
    if classification == "contango":
        return config.RED
    return config.BLUE


# Figure 1: today's curve. x-axis shows real delivery months.
def curve_snapshot(number, prices, classification, x_labels):
    colour = shape_colour(classification)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_labels, y=prices.values,
        mode="lines+markers",
        line=dict(color=colour, width=3),
        marker=dict(size=11, color=colour),
    ))
    return style(fig, number, "Current shape of the curve",
                xtitle="Delivery month",
                ytitle=f"Price ({config.PRICE_UNIT})")


# Figure 2: curve overlaid at several points in time (today, 1y ago, ...).
def curve_evolution(number, curves):
    fig = go.Figure()
    palette = [config.BLUE, config.GOLD, config.GREEN, config.RED]
    x_labels = ["Month 1", "Month 2", "Month 3", "Month 4"]
    i = 0
    for label, series in curves.items():
        if series is None or len(series) == 0:
            continue
        x = x_labels[:len(series)]
        fig.add_trace(go.Scatter(
            x=x, y=series.values,
            mode="lines+markers",
            line=dict(color=palette[i % len(palette)], width=2.4),
            marker=dict(size=7),
            name=label,
        ))
        i += 1
    return style(fig, number, "Curve shape at different points in time",
                legend=True,
                xtitle="Delivery month (numbered from the nearest)",
                ytitle=f"Price ({config.PRICE_UNIT})")


# Figure 3: holding return over time
def holding_return_timeseries(number, series):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=series.index, y=series.values * 100,
        mode="lines",
        line=dict(color=config.GOLD, width=1.6),
    ))
    # Reference line at zero so the user can tell paying from costing
    fig.add_hline(y=0, line=dict(color=config.GREY, width=1, dash="dash"))
    return style(fig, number, "Holding return over time",
                ytitle="Holding return per year (percent)")


# Figure 4: price line vs cumulative carry, both rebased to 1
def carry_vs_price(number, carry, front_norm):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=front_norm.index, y=front_norm.values,
        mode="lines",
        line=dict(color=config.BLUE, width=1.8),
        name="Nearest price (rebased to 1.0)",
    ))
    fig.add_trace(go.Scatter(
        x=carry.index, y=carry.values,
        mode="lines",
        line=dict(color=config.GOLD, width=1.8),
        name="Pure holding return, compounded",
    ))
    return style(fig, number, "Price change versus pure holding return",
                legend=True, ytitle="Index, starting value is 1.0")


# Figure 5: question 1 bar chart - avg forward return after falling vs
# rising curve, at each of the three horizons.
def horizon_comparison_chart(number, horizon_df):
    fig = go.Figure()
    # One bar series for falling-curve days, one for rising-curve days
    fig.add_trace(go.Bar(
        x=horizon_df["horizon"], y=horizon_df["falling"],
        name="After a falling curve",
        marker_color=config.GREEN,
        text=[f"{v:+.1f}%" for v in horizon_df["falling"]],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        x=horizon_df["horizon"], y=horizon_df["rising"],
        name="After a rising curve",
        marker_color=config.RED,
        text=[f"{v:+.1f}%" for v in horizon_df["rising"]],
        textposition="outside",
    ))
    # Group the bars side by side, not stacked
    fig.update_layout(barmode="group")
    # Reference line at zero
    fig.add_hline(y=0, line=dict(color=config.GREY, width=1))

    # Give the chart some headroom so labels above the bars don't get cut off
    all_values = list(horizon_df["falling"]) + list(horizon_df["rising"])
    # Filter out NaN entries with a regular if-check
    valid = [v for v in all_values if v == v]   # v == v is False only for NaN
    if valid:
        biggest = max(abs(v) for v in valid)
        fig.update_yaxes(range=[-biggest * 1.6, biggest * 1.6])

    return style(fig, number,
                "Forward returns after a falling curve versus after a rising curve",
                legend=True, height=420,
                xtitle="Forecast horizon",
                ytitle="Average price return (percent)")


# Figure 6: question 2 three-bucket bar chart
def inventory_buckets_chart(number, buckets):
    labels = ["Low inventory", "Normal inventory", "High inventory"]
    values = [buckets["low_mean"], buckets["mid_mean"], buckets["high_mean"]]
    counts = [buckets["low_n"], buckets["mid_n"], buckets["high_n"]]
    colours = [config.GREEN, config.GREY, config.RED]
    # Label format: "+1.2% (35 weeks)"
    text = [f"{v:+.1f}% ({c} weeks)" for v, c in zip(values, counts)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=values, marker_color=colours,
        text=text, textposition="outside",
    ))
    fig.add_hline(y=0, line=dict(color=config.GREY, width=1))

    # Add headroom for the labels
    valid = [v for v in values if v == v]   # NaN check
    if valid:
        biggest = max(abs(v) for v in valid)
        fig.update_yaxes(range=[-biggest * 1.6, biggest * 1.6])

    return style(fig, number, "Average holding return by inventory level",
                height=400,
                ytitle="Average holding return per year (percent)")
