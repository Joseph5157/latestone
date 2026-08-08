"""Transformer detail page shell — layout only, no queries."""
from __future__ import annotations

import dash_html_components as html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.entity_table import entity_table


def layout(plant_name: str = "", transformer_code: str = "") -> html.Div:
    return html.Div(
        className="page page--transformer-detail",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([
                    ("Plants", "/plants"),
                    (plant_name or "Plant", f"/plants"),
                    (transformer_code or "Transformer", None),
                ]),
            ),
            html.H1(transformer_code or "Transformer"),
            entity_table(
                table_id="devices-table",
                columns=[
                    {"name": "Device", "id": "device_code", "type": "text"},
                    {"name": "Status", "id": "status", "type": "text"},
                ],
                rows=[],
            ),
        ],
    )
