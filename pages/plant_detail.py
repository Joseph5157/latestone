"""Plant detail page shell — layout only, no queries."""
from __future__ import annotations

from dash import html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.entity_table import entity_table
from components.status_panels import inactive_notice


def layout(plant_name: str = "", status: str = "") -> html.Div:
    return html.Div(
        # page--monitoring: Plant is a hierarchy/dashboard screen like Fleet,
        # not a reading-width page like Device (§11).
        className="page page--monitoring page--plant-detail",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([
                    # Label only — the route stays /plants (spec §3.1).
                    ("Fleet", "/plants"),
                    (plant_name or "Plant", None),
                ]),
            ),
            inactive_notice("plant") if status == "inactive" else None,
            html.H1(plant_name or "Plant"),
            html.P(
                "Transformers in this plant, worst data first",
                className="page__subtitle",
            ),
            # Filled by the listing callback when a query fails, so an
            # unreachable database does not look like an empty result.
            html.Div(id="transformers-error", className="listing-error"),
            html.Section(
                className="detail-operational-summary",
                children=[
                    html.Div(
                        className="detail-section-heading",
                        children=[
                            html.H2("Operational summary"),
                            html.P("Current monitoring view for this plant"),
                        ],
                    ),
                    # Identity facts and counts come from the same already-scoped
                    # callback result as the inventory below.
                    html.Div(id="plant-context"),
                    html.Div(
                        className="detail-operational-summary__signals",
                        children=[
                            # Same callback, same FleetHealth as the table below it.
                            html.Div(id="plant-kpis"),
                            # Maximum latest temperature only — attribution, not alarm.
                            html.Div(id="plant-attribution"),
                        ],
                    ),
                ],
            ),
            html.Section(
                className="detail-metric-section",
                children=[
                    html.Div(
                        className="detail-section-heading",
                        children=[
                            html.H2("Metric health"),
                            html.P("Reporting freshness by configured metric"),
                        ],
                    ),
                    # One tile per configured metric, scoped to this plant's devices.
                    html.Div(id="plant-metric-health"),
                ],
            ),
            html.H2("Transformer inventory", className="detail-inventory__title"),
            entity_table(
                table_id="transformers-table",
                columns=[
                    {"name": "Transformer", "id": "transformer_code", "type": "text"},
                    {"name": "Status", "id": "status", "type": "text"},
                    {"name": "Data", "id": "freshness", "type": "text"},
                ],
                rows=[],
                link_column_id="transformer",
                state_column_id="freshness",
                administrative_state_column_id="status",
                responsive=True,
            ),
        ],
    )
