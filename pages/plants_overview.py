"""Plants overview page shell — layout only, no queries."""
from __future__ import annotations

from dash import html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.entity_table import entity_table


def layout() -> html.Div:
    return html.Div(
        className="page page--plants-overview",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([("Plants", None)]),
            ),
            html.H1("Plants"),
            # Filled by the listing callback when a query fails, so an
            # unreachable database does not look like an empty result.
            html.Div(id="plants-error", className="listing-error"),
            entity_table(
                table_id="plants-table",
                columns=[
                    {"name": "Plant", "id": "plant_id", "type": "text"},
                    {"name": "Country", "id": "country", "type": "text"},
                    {"name": "Primary Fuel", "id": "primary_fuel", "type": "text"},
                    {"name": "Capacity (MW)", "id": "capacity_mw", "type": "numeric"},
                    {"name": "Transformers", "id": "transformers", "type": "numeric"},
                    {"name": "Devices", "id": "devices", "type": "numeric"},
                ],
                rows=[],
                link_column_id="plant",
            ),
        ],
    )
