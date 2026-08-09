"""Plant detail page shell — layout only, no queries."""
from __future__ import annotations

from dash import html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.entity_table import entity_table
from components.status_panels import inactive_notice


def layout(plant_name: str = "", status: str = "") -> html.Div:
    return html.Div(
        className="page page--plant-detail",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([
                    ("Plants", "/plants"),
                    (plant_name or "Plant", None),
                ]),
            ),
            inactive_notice("plant") if status == "inactive" else None,
            html.H1(plant_name or "Plant"),
            # Filled by the listing callback when a query fails, so an
            # unreachable database does not look like an empty result.
            html.Div(id="transformers-error", className="listing-error"),
            entity_table(
                table_id="transformers-table",
                columns=[
                    {"name": "Transformer", "id": "transformer_code", "type": "text"},
                    {"name": "Status", "id": "status", "type": "text"},
                ],
                rows=[],
                link_column_id="transformer",
            ),
        ],
    )
