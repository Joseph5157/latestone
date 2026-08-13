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

from components.chart_presentation import TEMPLATE, grid_axis, hover_template, no_data_annotation
from components.metric_chart import BAR_COLOR, LINE_COLOR
from config.metrics import Aggregation, format_value, ordered_metrics
from routes import device_href
from services.monitoring_service import ConsumptionBar, MetricView

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
        template=TEMPLATE,
        showlegend=False,
        dragmode=False,
        # Deliberately not grid_axis(): a sparkline hides its x-gridlines,
        # unlike the primary chart.
        xaxis=dict(showgrid=False, nticks=4, title=None),
        yaxis=grid_axis(nticks=3, title=None),
    )


def cell_figure(view: MetricView, bars: list[ConsumptionBar]) -> go.Figure:
    """One sparse trace. Bars for a cumulative meter, a line for everything else
    — the same rule as the primary chart, so a metric never changes shape
    between the cell and the chart above it.

    `bars` is already-binned data for a delta metric, prepared by
    `monitoring_service.quick_trend_bars` and threaded down from the
    callback — this function decides which shape to draw, never how the bars
    were computed.
    """
    metric = view.metric
    fig = go.Figure()

    if not view.series:
        fig.add_annotation(**no_data_annotation("No readings in this period", size=11))
    elif metric.aggregation is Aggregation.DELTA:
        fig.add_trace(
            go.Bar(
                x=[b.start for b in bars],
                y=[b.result.value if b.result.is_known else None for b in bars],
                marker_color=BAR_COLOR,
                hovertemplate=hover_template(metric),
            )
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=[r.timestamp for r in view.series],
                y=[r.value for r in view.series],
                mode="lines",
                line=dict(color=LINE_COLOR, width=1.5),
                hovertemplate=hover_template(metric),
            )
        )

    fig.update_layout(**_cell_layout())
    return fig


def trend_cell(
    view: MetricView,
    bars: list[ConsumptionBar],
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
                        figure=cell_figure(view, bars),
                        config=TREND_CHART_CONFIG,
                        className="trend-cell__chart",
                    ),
                ],
            )
        ],
    )


def trend_grid(
    views: dict,
    quick_trend_bars: dict,
    active_metric_key: str,
    device_id: str,
    period: str | None = None,
    custom_start: str | None = None,
    custom_end: str | None = None,
) -> html.Div:
    """Eight cells in display order. Always eight, always the same order.

    `quick_trend_bars` carries already-binned data per delta metric, built by
    `monitoring_service.quick_trend_bars` and passed in by the callback; a
    metric with no entry (every statistics metric) simply gets an empty list,
    which `cell_figure` never looks at for a non-delta metric.
    """
    return html.Div(
        className="trend-grid",
        children=[
            trend_cell(
                views[m.key], quick_trend_bars.get(m.key, []),
                m.key == active_metric_key, device_id,
                period=period, custom_start=custom_start, custom_end=custom_end,
            )
            for m in ordered_metrics() if m.key in views
        ],
    )
