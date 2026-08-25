"""Plants overview page shell — layout only, no queries."""
from __future__ import annotations

from dash import html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.entity_table import entity_table


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--plants-overview",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([("Fleet", None)]),
            ),
            html.H1("Fleet Overview"),
            # Filled by the listing callback so the count comes from the same
            # hierarchy query as the Plants card, never a literal.
            html.P(id="fleet-subtitle", className="page__subtitle"),
            # Filled by the listing callback with an absolute UTC render
            # stamp — the same instant passed to get_fleet_health(), so this
            # line and the table's freshness column can never disagree about
            # what "now" was.
            html.P(id="fleet-refreshed", className="page__meta"),
            # Filled by the listing callback when a query fails, so an
            # unreachable database does not look like an empty result.
            html.Div(id="plants-error", className="listing-error"),
            # Reading order (ENT-2): state -> exceptions -> hierarchy ->
            # inventory -> administration. Everything above the inventory is
            # monitoring; administration is deliberately last and secondary.
            html.Section(
                className="fleet-monitoring-summary",
                children=[
                    html.H2("Operating status", className="fleet-section__title"),
                    # Structural fleet totals and the primary Data Health block
                    # are filled from the same callback/FleetHealth instance.
                    html.Div(id="fleet-kpis"),
                    html.Div(id="fleet-health-distribution"),
                ],
            ),
            # Presentation-only exact-condition summary, built from the same
            # already-available health counts. Empty for mixed populations.
            html.Div(id="fleet-systemic-state"),
            # Grouped exception queue (Plant -> Transformer -> RTL). The
            # component discloses truthful totals and links to the
            # authoritative inventory below.
            html.Div(id="needs-attention"),
            html.H2(
                "Fleet / Plants",
                id="fleet-plants",
                className="fleet-inventory__title",
            ),
            entity_table(
                table_id="plants-table",
                # Deliberately duplicated from callbacks.listings.PLANT_COLUMNS
                # rather than imported: pages define layout, callbacks consume
                # it, and a page importing its own callback module inverts that.
                # The callback replaces these on first fire; this spec is what
                # renders for the first paint, so it must agree. A test asserts
                # the two stay identical.
                columns=[
                    {"name": "Plant", "id": "plant"},
                    {"name": "Country", "id": "country"},
                    {"name": "Fuel", "id": "fuel"},
                    {"name": "Capacity (MW)", "id": "capacity_mw", "type": "numeric"},
                    {"name": "Transformers", "id": "transformers", "type": "numeric"},
                    {"name": "Devices", "id": "devices", "type": "numeric"},
                    {"name": "Data", "id": "freshness"},
                ],
                rows=[],
                link_column_id="plant",
                state_column_id="freshness",
                responsive=True,
            ),
            # Filled by the same callback from one AdminOverviewSummary, at the
            # same instant as the freshness figures above. Administration is a
            # separate axis from monitoring: these cards count Managed RTLs,
            # the Devices card above counts Monitoring Devices, and the two
            # populations are labelled rather than reconciled. The section
            # heading is supplied by the component, not this layout, so a
            # failed read drops the heading with the cards.
            #
            # Holds the whole Administration section: the three cards and the
            # Unassigned RTLs panel beneath them (ADMIN-3), both built from
            # the same summary in the same error boundary. One slot, so a
            # failed read cannot leave half a section standing. It sits BELOW
            # the fleet inventory by design: an operator opens this page for
            # state, exceptions and plants — never for administration.
            html.Div(id="admin-summary", className="fleet-administration"),
        ],
    )
