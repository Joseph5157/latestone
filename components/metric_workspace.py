"""Metric workspace — one merged cell per metric (ENT-3).

Replaces the former snapshot strip + Quick Trends pair, which rendered every
metric's label and latest value twice. A cell now carries the whole signal in
one place: label, freshness state, latest value, direction versus the period
start, and the trend shape itself.

Interaction authority is singular: each cell is exactly one link that promotes
that metric to the primary chart through `device_href`, so the metric/period/
custom-bounds URL state survives promotion unchanged. There are no secondary
click targets and no per-cell modebars — eight toolbars would compete with the
primary chart, which remains where zoom/pan lives.

The Current/Minimum/Maximum/Average detail deliberately stays OUT of these
cells; it belongs to the KPI row of whichever metric is selected. Eight compact
signals, not eight miniature dashboards.

Presentation only. Every number here is read off a MetricView built by the one
fetch the device callback makes; this module never queries and never computes.
"""
from __future__ import annotations

from dash import dcc, html
import plotly.graph_objects as go

from components.chart_presentation import (
    TEMPLATE, bar_geometries, grid_axis, hover_template, no_data_annotation,
)
from components.freshness_badge import freshness_badge
from components.metric_chart import BAR_COLOR, LINE_COLOR
from config.metrics import Aggregation, MetricConfig, format_value, ordered_metrics
from routes import device_href
from services.monitoring_service import ConsumptionBar, DeltaResult, MetricView

WORKSPACE_CELL_HEIGHT = 120
"""Fixed, and applied to empty cells too. A cell that collapsed when a metric
had no readings would read as a layout fault rather than as absent data."""

#: No modebar: eight more toolbars would compete with the primary chart for
#: attention. Dragging is off for the same reason. Hover stays on — §21 requires
#: the absolute UTC instant to be reachable.
WORKSPACE_CHART_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "responsive": True,
    "displaylogo": False,
}

EMPTY_PERIOD_TEXT = "No data available for the selected period"
"""Shared with the primary chart (metric_chart.py): one phrase for one
condition, so the page cannot imply two different kinds of absence."""


def direction_text(metric: MetricConfig, change: DeltaResult) -> str:
    """Signed change against the period start, or an em dash when unknown.

    The arrow carries the direction and the number carries the magnitude, so a
    fall reads "▼ 0.31 kV" rather than "▼ -0.31 kV" — one sign, not two.
    Neutral by design: up/down is change, not health, so no colour semantics
    attach to it.

    A cumulative meter whose delta is indeterminate shows the dash rather than a
    negative, which would read as generation.
    """
    if not change.is_known or change.value is None:
        return "—"
    if change.value > 0:
        return f"▲ +{format_value(metric, change.value)}"
    if change.value < 0:
        return f"▼ {format_value(metric, abs(change.value))}"
    return format_value(metric, change.value)


def _cell_layout() -> dict:
    return dict(
        margin=dict(l=36, r=8, t=6, b=22),
        height=WORKSPACE_CELL_HEIGHT,
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
        fig.add_annotation(**no_data_annotation(EMPTY_PERIOD_TEXT, size=11))
    elif metric.aggregation is Aggregation.DELTA:
        geometries = bar_geometries(bars)
        fig.add_trace(
            go.Bar(
                x=[g.x for g in geometries],
                y=[b.result.value if b.result.is_known else None for b in bars],
                width=[g.width_ms for g in geometries],
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


def metric_cell(
    view: MetricView,
    bars: list[ConsumptionBar],
    is_selected: bool,
    device_id: str,
    period: str | None = None,
    custom_start: str | None = None,
    custom_end: str | None = None,
) -> html.Div:
    """One merged cell. The whole cell is ONE link, so clicking anywhere
    promotes — value and sparkline are never separate targets."""
    metric = view.metric
    # Selection styling only. "The one you are looking at" and "the one with a
    # problem" are different statements and must not share a colour, so no
    # warning class ever appears here; freshness rides on its own badge.
    classes = "metric-cell metric-cell--selected" if is_selected else "metric-cell"
    return html.Div(
        className=classes,
        children=[
            dcc.Link(
                href=device_href(
                    device_id, metric_key=metric.key, period=period,
                    start=custom_start, end=custom_end,
                ),
                className="metric-cell__link",
                children=[
                    html.Div(
                        className="metric-cell__header",
                        children=[
                            html.Span(metric.label, className="metric-cell__label"),
                            freshness_badge(view.freshness),
                        ],
                    ),
                    html.Div(
                        format_value(metric, view.current),
                        className="metric-cell__value",
                    ),
                    # Always rendered, em dash when unknown, so every cell keeps
                    # one height — a stepping row would push the primary chart
                    # down past the §6.8 budget.
                    html.Div(
                        direction_text(metric, view.change),
                        className="metric-cell__direction",
                    ),
                    dcc.Graph(
                        figure=cell_figure(view, bars),
                        config=WORKSPACE_CHART_CONFIG,
                        className="metric-cell__chart",
                    ),
                ],
            )
        ],
    )


def metric_workspace(
    views: dict,
    quick_trend_bars: dict,
    active_metric_key: str,
    device_id: str,
    period: str | None = None,
    custom_start: str | None = None,
    custom_end: str | None = None,
) -> html.Div:
    """Eight cells in registry display order. Always eight, always the same
    order — cell location becomes muscle memory.

    `quick_trend_bars` carries already-binned data per delta metric, built by
    `monitoring_service.quick_trend_bars` and passed in by the callback; a
    metric with no entry (every statistics metric) simply gets an empty list,
    which `cell_figure` never looks at for a non-delta metric.
    """
    return html.Div(
        className="metric-workspace",
        children=[
            metric_cell(
                views[m.key], quick_trend_bars.get(m.key, []),
                m.key == active_metric_key, device_id,
                period=period, custom_start=custom_start, custom_end=custom_end,
            )
            for m in ordered_metrics() if m.key in views
        ],
    )
