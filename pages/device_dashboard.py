"""Device dashboard page shell — layout only, no queries."""
from __future__ import annotations

import dash_core_components as dcc
import dash_html_components as html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.metric_chart import metric_chart
from components.readings_table import readings_table
from config.metrics import ordered_metrics
from config.settings import monitoring


def layout(
    plant_name: str = "",
    transformer_code: str = "",
    device_code: str = "",
) -> html.Div:
    metric_options = [{"label": m.label, "value": m.key} for m in ordered_metrics()]

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
            ),
            html.Div(id="equipment-context-container"),
            html.Div(id="snapshot-strip"),
            html.Div(
                className="metric-controls",
                children=[
                    dcc.Dropdown(
                        id="metric-dropdown",
                        options=metric_options,
                        value=metric_options[0]["value"] if metric_options else None,
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
                        value="24h",
                        inline=True,
                        className="period-radio",
                    ),
                    html.Div(
                        id="custom-range-container",
                        style={"display": "none"},
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
