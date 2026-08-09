"""Quick Trends — one small chart per metric, always all eight.

Positions never reflow, so cell location becomes muscle memory. Interaction
lives in the primary chart: these cells carry no modebar, and clicking one
promotes that metric upward through the same `device_href` contract the snapshot
tiles use, so period and custom bounds survive without a new URL parameter.

Presentation only. Every number here is read off a MetricView built by the one
fetch the device callback makes; this module never queries and never computes.
"""
from __future__ import annotations

from dash import dcc, html
import plotly.graph_objects as go

from components.metric_chart import BAR_COLOR, LINE_COLOR
from config.metrics import Aggregation, format_value, ordered_metrics
from routes import device_href
from services.monitoring_service import MetricView, bin_consumption, choose_bin

TREND_CELL_HEIGHT = 120
"""Fixed, and applied to empty cells too. A cell that collapsed when a metric
had no readings would read as a layout fault rather than as absent data."""

#: No modebar: eight more toolbars would compete with the primary chart for
#: attention. Dragging is off for the same reason. Hover stays on — §21 requires
#: the absolute UTC instant to be reachable.
TREND_CHART_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "responsive": True,
    "displaylogo": False,
}


def _cell_layout() -> dict:
    return dict(
        margin=dict(l=36, r=8, t=6, b=22),
        height=TREND_CELL_HEIGHT,
        template="plotly_white",
        showlegend=False,
        dragmode=False,
        xaxis=dict(showgrid=False, nticks=4, title=None),
        yaxis=dict(showgrid=True, gridcolor="#eef0f3", nticks=3, title=None),
    )


def _hover(metric) -> str:
    return (
        "%{x|%Y-%m-%d %H:%M} UTC<br>%{y:."
        + str(metric.precision) + "f} " + metric.unit + "<extra></extra>"
    )


def cell_figure(view: MetricView) -> go.Figure:
    """One sparse trace. Bars for a cumulative meter, a line for everything else
    — the same rule as the primary chart, so a metric never changes shape
    between the cell and the chart above it."""
    metric = view.metric
    fig = go.Figure()

    if not view.series:
        fig.add_annotation(
            text="No readings in this period",
            showarrow=False, font=dict(size=11, color="#6b7280"),
        )
    elif metric.aggregation is Aggregation.DELTA:
        start, end = view.series[0].timestamp, view.series[-1].timestamp
        bars = bin_consumption(view.series, choose_bin(end - start), start, end)
        fig.add_trace(
            go.Bar(
                x=[b.start for b in bars],
                y=[b.result.value if b.result.is_known else None for b in bars],
                marker_color=BAR_COLOR,
                hovertemplate=_hover(metric),
            )
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=[r.timestamp for r in view.series],
                y=[r.value for r in view.series],
                mode="lines",
                line=dict(color=LINE_COLOR, width=1.5),
                hovertemplate=_hover(metric),
            )
        )

    fig.update_layout(**_cell_layout())
    return fig


def trend_cell(
    view: MetricView,
    is_selected: bool,
    device_id: str,
    period: str | None = None,
    custom_start: str | None = None,
    custom_end: str | None = None,
) -> html.Div:
    """One cell. The whole cell is a link, so clicking anywhere promotes."""
    metric = view.metric
    # Selection styling only. "The one you are looking at" and "the one with a
    # problem" are different statements and must not share a colour, so no
    # freshness or warning class ever appears here.
    classes = "trend-cell trend-cell--selected" if is_selected else "trend-cell"
    return html.Div(
        className=classes,
        children=[
            dcc.Link(
                href=device_href(
                    device_id, metric_key=metric.key, period=period,
                    start=custom_start, end=custom_end,
                ),
                className="trend-cell__link",
                children=[
                    html.Div(
                        className="trend-cell__header",
                        children=[
                            html.Span(metric.label, className="trend-cell__label"),
                            html.Span(
                                format_value(metric, view.current),
                                className="trend-cell__value",
                            ),
                        ],
                    ),
                    dcc.Graph(
                        figure=cell_figure(view),
                        config=TREND_CHART_CONFIG,
                        className="trend-cell__chart",
                    ),
                ],
            )
        ],
    )


def trend_grid(
    views: dict,
    active_metric_key: str,
    device_id: str,
    period: str | None = None,
    custom_start: str | None = None,
    custom_end: str | None = None,
) -> html.Div:
    """Eight cells in display order. Always eight, always the same order."""
    return html.Div(
        className="trend-grid",
        children=[
            trend_cell(
                views[m.key], m.key == active_metric_key, device_id,
                period=period, custom_start=custom_start, custom_end=custom_end,
            )
            for m in ordered_metrics() if m.key in views
        ],
    )
