"""Device dashboard page shell — layout only, no queries."""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.metric_chart import metric_chart
from components.readings_table import readings_table
from config.metrics import ordered_metrics
from config.settings import monitoring
from services.monitoring_service import Freshness


def layout(
    plant_name: str = "",
    transformer_code: str = "",
    device_code: str = "",
    metric_key: str | None = None,
    period: str | None = None,
) -> html.Div:
    metric_options = [{"label": m.label, "value": m.key} for m in ordered_metrics()]
    initial_metric = metric_key or (metric_options[0]["value"] if metric_options else None)
    initial_period = period or "24h"

    return html.Div(
        className="page page--device-dashboard",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([
                    ("Plants", "/plants"),
                    (plant_name or "Plant", None),
                    (transformer_code or "Transformer", None),
                    (device_code or "Device", None),
                ]),
                freshness=Freshness.NO_DATA,
            ),
            html.Div(
                id="equipment-context-container",
                className="equipment-context",
                children=[
                    html.Span("Last data: ", className="equipment-context__label"),
                    html.Span(id="equipment-last-data", className="equipment-context__value"),
                ],
            ),
            html.Div(id="snapshot-strip"),
            html.Div(
                className="metric-controls",
                children=[
                    dcc.Dropdown(
                        id="metric-dropdown",
                        options=metric_options,
                        value=initial_metric,
                        clearable=False,
                        searchable=False,
                        className="metric-dropdown",
                    ),
                    dcc.RadioItems(
                        id="period-radio",
                        options=[
                            {"label": " 24h", "value": "24h"},
                            {"label": " 7d", "value": "7d"},
                            {"label": " 30d", "value": "30d"},
                            {"label": " Custom", "value": "custom"},
                        ],
                        value=initial_period,
                        inline=True,
                        className="period-radio",
                    ),
                    html.Div(
                        id="custom-range-container",
                        style={"display": "block" if initial_period == "custom" else "none"},
                        children=[
                            dcc.DatePickerRange(
                                id="custom-date-range",
                                display_format="YYYY-MM-DD",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(id="kpi-row-container"),
            dcc.Loading(
                metric_chart("metric-chart"),
                className="chart-loading",
            ),
            readings_table("readings-table"),
            dcc.Interval(
                id="device-refresh-interval",
                interval=monitoring.refresh_interval_seconds * 1000,
            ),
        ],
    )
