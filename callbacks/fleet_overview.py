"""The Fleet Overview's one callback (SATURDAY-REAL-FLEET-01).

One page load = one scope resolution (ADR-004) = one `rtl_fleet_service`
snapshot = every output. The data is the read-only client RTL SQL Server; there
is no PostgreSQL or synthetic fallback. An unreachable source shows the shared
error panel, never an empty fleet. Roles without an approved raw-RTL
visibility rule get an explicit restricted panel and the RTL source is not
read for them.

A filter chip change re-runs the same path: one fresh snapshot, narrowed by
`filter_rows`, with the chip counts taken from that same snapshot.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from dash import Input, Output, no_update

from components import rtl_fleet as ui
from components.status_panels import error_panel
from pages import plants_overview as page
from services.device_scope import current_device_scope
from services.rtl_fleet_service import FleetStatus, get_real_fleet, may_view_real_fleet

logger = logging.getLogger(__name__)

ROUTE = "overview"
OUTPUTS = 5  # stat cards, refreshed, list, error, filter options


def populate(context, filter_key=ui.FILTER_ALL, *,
             fetch=get_real_fleet, scope_for=current_device_scope):
    """Body of the callback, testable without a Dash runtime."""
    if not context or context.get("route") != ROUTE:
        return (no_update,) * OUTPUTS
    try:
        scope = scope_for()
        if not may_view_real_fleet(scope):
            return None, None, ui.restricted_panel(), None, []
        now = datetime.now(timezone.utc)
        fleet = fetch()
    except Exception:
        logger.exception("Failed to load the Fleet Overview")
        return None, None, [], error_panel(), []
    if fleet.status is not FleetStatus.DATA or fleet.summary is None:
        return None, None, [], error_panel(
            "The client RTL data source is unavailable. No RTL data is shown."
        ), []
    return (
        ui.summary_cards(fleet.summary),
        f"Updated {now.strftime('%d %b %Y %H:%M UTC')}",
        ui.fleet_table(ui.filter_rows(fleet, filter_key or ui.FILTER_ALL)),
        None,
        ui.filter_options(fleet),
    )


def register(app) -> None:
    @app.callback(
        Output(page.STATS_ID, "children"),
        Output(page.REFRESHED_ID, "children"),
        Output(page.LIST_ID, "children"),
        Output(page.ERROR_ID, "children"),
        Output(page.FILTER_ID, "options"),
        Input("page-context", "data"),
        Input(page.FILTER_ID, "value"),
    )
    def populate_fleet_overview(context, filter_key):
        return populate(context, filter_key)
