"""Plant detail page shell — layout only, no queries."""
from __future__ import annotations

from dash import html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.entity_table import entity_table


def layout(plant_name: str = "") -> html.Div:
    return html.Div(
        className="page page--plant-detail",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([
                    ("Plants", "/plants"),
                    (plant_name or "Plant", None),
                ]),
            ),
            html.H1(plant_name or "Plant"),
            entity_table(
                table_id="transformers-table",
                columns=[
                    {"name": "Transformer", "id": "transformer_code", "type": "text"},
                    {"name": "Status", "id": "status", "type": "text"},
                ],
                rows=[],
            ),
        ],
    )
