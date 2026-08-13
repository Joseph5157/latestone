"""Metric chart — line chart parameterized by MetricConfig."""
from __future__ import annotations

from dash import dcc
import plotly.graph_objects as go

from components.chart_presentation import TEMPLATE, grid_axis, hover_template, no_data_annotation
from config.metrics import MetricConfig
from services.monitoring_service import Reading

LINE_COLOR = "#3b82f6"


CHART_HEIGHT = 340
"""Sized so the x-axis and its title stay inside a 768 px viewport when the
chart starts at the section 6.8 budget of 420 px. At the previous 380 px the
axis title fell below the fold."""


def _axis_title(metric: MetricConfig) -> str:
    """Unit only. The metric name lives in the chart title, so repeating it here
    just widened the left margin — at `l=40` the rotated "Temperature (°C)" was
    being clipped to "perature (°C)"."""
    return metric.unit or ""


def _chart_title(metric: MetricConfig, period_label: str | None) -> str:
    """Metric and period in the chart header (spec section 18).

    Rendered inside the figure rather than as an HTML panel header, so it costs
    plot height rather than page height and cannot push the chart past the
    section 6.8 budget."""
    if period_label:
        return f"{metric.label} ({metric.unit}) &#183; {period_label}" if metric.unit             else f"{metric.label} &#183; {period_label}"
    return f"{metric.label} ({metric.unit})" if metric.unit else metric.label


def _apply_common_layout(
    fig: go.Figure,
    metric: MetricConfig,
    title_text: str,
    view_revision: str | None,
    **extra,
) -> None:
    """Layout shared by `build_metric_figure` and `build_delta_figure`: same
    margin/height budget, same title placement, same axis language. Only the
    traces above and the title text differ between a line and a delta-bar
    chart — `extra` carries the one further difference, `hovermode`, which
    `build_delta_figure` does not set.
    """
    fig.update_layout(
        margin=dict(l=56, r=20, t=44, b=48),
        height=CHART_HEIGHT,
        title=dict(text=title_text, x=0, xanchor="left", font=dict(size=14)),
        xaxis_title="Time (UTC)",
        yaxis_title=_axis_title(metric),
        template=TEMPLATE,
        showlegend=False,
        xaxis=grid_axis(),
        yaxis=grid_axis(),
        uirevision=view_revision or metric.key,
        **extra,
    )


def chart_revision(
    metric_key: str,
    period: str | None,
    custom_start: str | None,
    custom_end: str | None,
) -> str:
    """Identity of the *view* the chart is showing.

    Plotly keeps the user's zoom/pan while `uirevision` is unchanged, so this
    must be stable across the periodic refresh of one view and different for
    every view the operator can switch to. Keying on the metric alone let a
    zoom taken on 24h persist into 30d, where it looked like a narrow slice of
    the new range.
    """
    return "|".join([
        metric_key or "",
        period or "",
        custom_start or "",
        custom_end or "",
    ])


def build_metric_figure(
    metric: MetricConfig,
    series: list[Reading],
    view_revision: str | None = None,
    period_label: str | None = None,
) -> go.Figure:
    """Line chart driven entirely by MetricConfig.

    No threshold line is drawn: no client-confirmed warning/critical
    thresholds exist. When they do, add them here, driven by config.
    """
    fig = go.Figure()
    if series:
        fig.add_trace(
            go.Scatter(
                x=[r.timestamp for r in series],
                y=[r.value for r in series],
                mode="lines",
                name=metric.label,
                line=dict(color=LINE_COLOR, width=2),
                hovertemplate=hover_template(metric),
            )
        )
    else:
        fig.add_annotation(**no_data_annotation("No data available for the selected period"))

    # Preserve zoom/pan across the refresh interval; reset when the operator
    # changes metric, period or custom bounds (uirevision, inside the helper).
    _apply_common_layout(
        fig, metric, _chart_title(metric, period_label), view_revision,
        hovermode="x unified",
    )
    return fig


BAR_COLOR = "#3b82f6"

#: Neutral, deliberately not the warning palette. A meter discontinuity is a
#: data-quality condition, not an electrical alarm — CLAUDE.md keeps the three
#: status concepts separate, and a red mark here would read as the third one.
DISCONTINUITY_COLOR = "#9ca3af"

_STATUS_TEXT = {
    "discontinuity": "Meter discontinuity — not computed",
    "insufficient_data": "Not enough readings in this interval",
}


def build_delta_figure(
    metric: MetricConfig,
    bars: list,
    view_revision: str | None = None,
    period_label: str | None = None,
    bin_label: str = "",
) -> go.Figure:
    """Interval consumption for a cumulative meter.

    Bars carry `DeltaResult`s. A bin we could not compute draws no bar and a
    neutral marker — never a zero, which would assert we measured no
    consumption, and never a negative, which would read as generation.
    """
    fig = go.Figure()
    if not bars:
        fig.add_annotation(**no_data_annotation("No data available for the selected period"))
    else:
        fig.add_trace(
            go.Bar(
                x=[b.start for b in bars],
                y=[b.result.value if b.result.is_known else None for b in bars],
                marker_color=BAR_COLOR,
                name=metric.label,
                hovertemplate=hover_template(metric),
            )
        )
        unknown = [b for b in bars if not b.result.is_known]
        if unknown:
            fig.add_trace(
                go.Scatter(
                    x=[b.start for b in unknown],
                    y=[0 for _ in unknown],
                    mode="markers",
                    marker=dict(color=DISCONTINUITY_COLOR, size=6, symbol="x"),
                    hovertext=[
                        _STATUS_TEXT.get(b.result.status.value, b.result.status.value)
                        for b in unknown
                    ],
                    hovertemplate="%{x|%Y-%m-%d %H:%M} UTC<br>%{hovertext}<extra></extra>",
                    showlegend=False,
                )
            )

    title = _chart_title(metric, period_label)
    if bin_label:
        title = f"{title} &#183; {bin_label}"

    _apply_common_layout(fig, metric, title, view_revision)
    return fig


# Validated against the installed Plotly 5.24.1 default 2D cartesian modebar —
# every name here is a button that actually renders. `sendDataToCloud` is NOT in
# the default set (it needs `showSendToCloud`), so listing it would be noise.
#
# `resetScale2d` is deliberately retained: zoom and pan are supported, so the
# operator needs a discoverable way back to the full period. Double-click also
# resets, but an undiscoverable gesture is not an acceptable sole escape route.
MODEBAR_REMOVED = [
    "select2d", "lasso2d",                             # meaningless on a time series
    "zoomIn2d", "zoomOut2d", "autoScale2d",            # drag-zoom + reset cover these
    "toggleSpikelines",                                # unified hover already does this
    "hoverClosestCartesian", "hoverCompareCartesian",  # hovermode is fixed by us
]

CHART_CONFIG = {
    "displayModeBar": True,
    "scrollZoom": True,
    "responsive": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": MODEBAR_REMOVED,
}


def metric_chart(chart_id: str = "metric-chart"):
    return dcc.Graph(
        id=chart_id,
        figure=go.Figure(),
        config=CHART_CONFIG,
        className="metric-chart",
    )
