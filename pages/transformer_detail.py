"""Transformer detail page shell — layout only, no queries."""
from __future__ import annotations

from dash import html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.entity_table import entity_table
from components.status_panels import inactive_notice


def layout(
    plant_name: str = "", transformer_code: str = "", plant_id: str = "", status: str = "",
) -> html.Div:
    return html.Div(
        # page--monitoring: Transformer is a hierarchy/dashboard screen like
        # Fleet and Plant, not a reading-width page like Device (§11).
        className="page page--monitoring page--transformer-detail",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([
                    # Label only — the route stays /plants (spec §3.1).
                    ("Fleet", "/plants"),
                    (plant_name or "Plant", f"/plants/{plant_id}" if plant_id else "/plants"),
                    (transformer_code or "Transformer", None),
                ]),
            ),
            inactive_notice("transformer") if status == "inactive" else None,
            html.H1(transformer_code or "Transformer"),
            html.P(
                "Devices on this transformer, worst data first",
                className="page__subtitle",
            ),
            # Filled by the listing callback when a query fails, so an
            # unreachable database does not look like an empty result.
            html.Div(id="devices-error", className="listing-error"),
            html.Section(
                className="detail-operational-summary",
                children=[
                    html.Div(
                        className="detail-section-heading",
                        children=[
                            html.H2("Operational summary"),
                            html.P("Current monitoring view for this transformer"),
                        ],
                    ),
                    # Plant/transformer identity and the visible RTL count.
                    html.Div(id="transformer-context"),
                    html.Div(
                        className="detail-operational-summary__signals",
                        children=[
                            # Same callback, same FleetHealth as the table below it.
                            html.Div(id="transformer-kpis"),
                            # Maximum latest temperature only — attribution, not alarm.
                            html.Div(id="transformer-attribution"),
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
                    # One tile per configured metric, scoped to this transformer's devices.
                    html.Div(id="transformer-metric-health"),
                ],
            ),
            html.H2("RTL inventory", className="detail-inventory__title"),
            entity_table(
                table_id="devices-table",
                columns=[
                    {"name": "Device", "id": "device_code", "type": "text"},
                    {"name": "Status", "id": "status", "type": "text"},
                    {"name": "Data", "id": "freshness", "type": "text"},
                ],
                rows=[],
                link_column_id="device",
                state_column_id="freshness",
                administrative_state_column_id="status",
                responsive=True,
                # TABLE-SORT-TEXT-1: Data renders a freshness label, not its
                # own sort order — `callbacks/listings.py` sorts `data` itself.
                sort_action="custom",
            ),
            html.Div(id="devices-empty"),
        ],
    )
