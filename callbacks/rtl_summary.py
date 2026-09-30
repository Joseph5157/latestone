"""Real-RTL summary on the Command Center (RTL-NETWORK-USE-01).

One ``rtl_fleet_service`` snapshot per page render (not polled), shown only
where ``may_view_real_fleet`` allows - the same rule as the Registered RTLs
list. A Technician, or any restricted scope, gets nothing: no counts, no
UIDs, no network data. A source failure hides the panel rather than showing
zeros; the synthetic Command Center content is untouched.
"""
from __future__ import annotations

import logging

from dash import Input, Output, no_update

from components import rtl_fleet as ui
from pages import command_center as page
from services.device_scope import current_device_scope
from services.rtl_fleet_service import FleetStatus, get_real_fleet, may_view_real_fleet

logger = logging.getLogger(__name__)

ROUTE = "command_center"


def populate(context, *, fetch=get_real_fleet, scope_for=current_device_scope):
    if not context or context.get("route") != ROUTE:
        return no_update
    try:
        if not may_view_real_fleet(scope_for()):
            return None
        fleet = fetch()
    except Exception:
        logger.exception("Failed to load the RTL summary")
        return None
    if fleet.status is not FleetStatus.DATA or fleet.summary is None:
        return None
    return ui.rtl_summary_panel(fleet.summary)


def register(app) -> None:
    @app.callback(Output(page.RTL_SUMMARY_ID, "children"), Input("page-context", "data"))
    def populate_rtl_summary(context):
        return populate(context)
