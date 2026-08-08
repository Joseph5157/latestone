"""Device dashboard page shell — layout only, no queries."""
from __future__ import annotations

import dash_core_components as dcc
import dash_html_components as html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.equipment_context import equipment_context
from components.metric_chart import metric_chart
from components.metric_snapshot_strip import metric_snapshot_strip
from components.kpi_card import kpi_row
from components.readings_table import readings_table


def layout(
    plant_name: str = "",
    transformer_code: str = "",
    device_code: str = "",
) -> html.Div:
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
            dcc.Loading(
                children=[
                    html.Div(id="equipment-context-container"),
                    html.Div(id="snapshot-strip-container"),
                    html.Div(id="metric-selector-container"),
                    html.Div(id="kpi-row-container"),
                    html.Div(id="period-filter-container"),
                    metric_chart(),
                    html.Div(id="readings-table-container"),
                ],
            ),
        ],
    )
