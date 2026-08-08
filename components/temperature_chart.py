"""Plotly temperature trend chart component."""
from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc

from config.settings import demo_device, warning_settings
from services.temperature_service import Reading

LINE_COLOR = "#2563eb"
THRESHOLD_COLOR = "#dc2626"


def build_temperature_figure(readings: list[Reading]) -> go.Figure:
    fig = go.Figure()

    if readings:
        timestamps = [r.timestamp for r in readings]
        temps = [r.temperature_c for r in readings]

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=temps,
                mode="lines",
                name=demo_device.metric_label,
                line=dict(color=LINE_COLOR, width=2),
                hovertemplate="%{x|%Y-%m-%d %H:%M}<br>%{y:.1f} " + demo_device.unit + "<extra></extra>",
            )
        )

        fig.add_hline(
            y=warning_settings.threshold_celsius,
            line=dict(color=THRESHOLD_COLOR, width=1, dash="dash"),
            annotation_text=f"Demo warning threshold ({warning_settings.threshold_celsius:.0f}{demo_device.unit})",
            annotation_position="top left",
            annotation_font_color=THRESHOLD_COLOR,
        )
    else:
        fig.add_annotation(
            text="No data available for the selected period",
            showarrow=False,
            font=dict(size=14, color="#6b7280"),
        )

    fig.update_layout(
        margin=dict(l=40, r=20, t=40, b=40),
        height=380,
        xaxis_title="Time",
        yaxis_title=f"Temperature ({demo_device.unit})",
        template="plotly_white",
        hovermode="x unified",
        showlegend=False,
    )
    return fig


def temperature_chart(id_prefix: str = ""):
    return dcc.Graph(
        id=f"{id_prefix}temperature-chart",
        figure=build_temperature_figure([]),
        config={"displayModeBar": True, "scrollZoom": True, "responsive": True},
        className="temperature-chart",
    )
