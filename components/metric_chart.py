"""Metric chart — line chart parameterized by MetricConfig."""
from __future__ import annotations

from dash import dcc
import plotly.graph_objects as go

from config.metrics import MetricConfig
from services.monitoring_service import Reading

LINE_COLOR = "#3b82f6"


def _axis_title(metric: MetricConfig) -> str:
    return f"{metric.label} ({metric.unit})" if metric.unit else metric.label


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
                hovertemplate=(
                    "%{x|%Y-%m-%d %H:%M}<br>%{y:."
                    + str(metric.precision)
                    + "f} "
                    + metric.unit
                    + "<extra></extra>"
                ),
            )
        )
    else:
        fig.add_annotation(
            text="No data available for the selected period",
            showarrow=False,
            font=dict(size=14, color="#6b7280"),
        )

    fig.update_layout(
        margin=dict(l=40, r=20, t=30, b=40),
        height=380,
        xaxis_title="Time",
        yaxis_title=_axis_title(metric),
        template="plotly_white",
        hovermode="x unified",
        showlegend=False,
        # Preserve zoom/pan across the refresh interval; reset when the
        # operator changes metric, period or custom bounds.
        uirevision=view_revision or metric.key,
    )
    return fig


def metric_chart(chart_id: str = "metric-chart"):
    return dcc.Graph(
        id=chart_id,
        figure=go.Figure(),
        config={"displayModeBar": True, "scrollZoom": True, "responsive": True},
        className="metric-chart",
    )
