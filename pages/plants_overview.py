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
                breadcrumb_children=breadcrumb([("Fleet", None)]),
            ),
            html.H1("Fleet Overview"),
            # Filled by the listing callback so the count comes from the same
            # hierarchy query as the Plants card, never a literal.
            html.P(id="fleet-subtitle", className="page__subtitle"),
            # Filled by the listing callback when a query fails, so an
            # unreachable database does not look like an empty result.
            html.Div(id="plants-error", className="listing-error"),
            # Filled by the same callback that fills the table, from the same
            # FleetHealth, so the card and the rows cannot disagree.
            html.Div(id="fleet-kpis"),
            entity_table(
                table_id="plants-table",
                columns=[
                    {"name": "Plant", "id": "plant_id", "type": "text"},
                    {"name": "Country", "id": "country", "type": "text"},
                    {"name": "Primary Fuel", "id": "primary_fuel", "type": "text"},
                    {"name": "Capacity (MW)", "id": "capacity_mw", "type": "numeric"},
                    {"name": "Transformers", "id": "transformers", "type": "numeric"},
                    {"name": "Devices", "id": "devices", "type": "numeric"},
                    {"name": "Data", "id": "freshness", "type": "text"},
                ],
                rows=[],
                link_column_id="plant",
                state_column_id="freshness",
            ),
        ],
    )
