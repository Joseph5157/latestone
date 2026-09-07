"""Plants overview page shell — layout only, no queries."""
from __future__ import annotations

from dash import dcc, html

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
            # Data Refresh Context: the render stamp beside a Refresh action.
            # The link is a plain full-page reload of this same route
            # (`refresh=True`) — the existing way this page's data has always
            # been refreshed — so it needs no new callback and cannot drift
            # from `populate_overview`.
            html.Div(
                className="fleet-refresh-context",
                children=[
                    # Filled by the listing callback with an absolute UTC
                    # render stamp — the same instant passed to
                    # get_fleet_health(), so this line and the table's
                    # freshness column can never disagree about what "now"
                    # was.
                    html.P(id="fleet-refreshed", className="page__meta"),
                    dcc.Link(
                        "Refresh",
                        href="/plants",
                        refresh=True,
                        className="fleet-refresh-context__action",
                    ),
                ],
            ),
            # Filled by the listing callback when a query fails, so an
            # unreachable database does not look like an empty result.
            html.Div(id="plants-error", className="listing-error"),
            # Layer 2 only: existing output slots, one shared service snapshot.
            html.Section(
                className="fleet-monitoring-summary fleet-condition",
                children=[
                    html.Div(className="fleet-condition__section-heading", children=[
                        html.H2("Fleet Condition", className="fleet-condition__section-title"),
                        html.P("Current status of RTL fleet monitoring", className="fleet-condition__subtitle"),
                    ]),
                    html.Div(className="fleet-condition__upper", children=[
                        html.Div(id="fleet-systemic-state", className="fleet-condition__primary"),
                        html.Div(id="fleet-health-distribution"),
                    ]),
                    html.Div(id="fleet-kpis"),
                ],
            ),
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
            # C08-AUTO-DISABLE-1: independent of the block above — its own
            # callback (callbacks/forwarding_schedule.py), its own capability
            # check, no shared query. See that module's docstring for why it
            # is deliberately not folded into administration_section.
            html.Div(id="auto-disable-override-panel", className="fleet-administration"),
        ],
    )
