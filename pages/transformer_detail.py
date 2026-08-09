"""Transformer detail page shell — layout only, no queries."""
from __future__ import annotations

from dash import html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.entity_table import entity_table


def layout(plant_name: str = "", transformer_code: str = "", plant_id: str = "") -> html.Div:
    return html.Div(
        className="page page--transformer-detail",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([
                    ("Plants", "/plants"),
                    (plant_name or "Plant", f"/plants/{plant_id}" if plant_id else "/plants"),
                    (transformer_code or "Transformer", None),
                ]),
            ),
            html.H1(transformer_code or "Transformer"),
            # Filled by the listing callback when a query fails, so an
            # unreachable database does not look like an empty result.
            html.Div(id="devices-error", className="listing-error"),
            entity_table(
                table_id="devices-table",
                columns=[
                    {"name": "Device", "id": "device_code", "type": "text"},
                    {"name": "Status", "id": "status", "type": "text"},
                ],
                rows=[],
                link_column_id="device",
            ),
        ],
    )
