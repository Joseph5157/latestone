"""Factual RTL dashboard callback (FACTUAL-DASHBOARD-01).

One dashboard snapshot per page load (not polled), shown only where
``may_view_real_fleet`` allows - the rule the Registered RTLs list uses. A
restricted scope gets nothing; a source failure shows an unavailable notice,
never zeros.
"""
from __future__ import annotations

import logging

from dash import Input, Output, no_update

from components import rtl_dashboard as ui
from pages import rtl_dashboard as page
from services.device_scope import current_device_scope
from services.rtl_dashboard_service import DashboardStatus, get_dashboard, may_view_dashboard

logger = logging.getLogger(__name__)

ROUTE = "rtl_dashboard"


def populate(context, *, fetch=get_dashboard, scope_for=current_device_scope):
    if not context or context.get("route") != ROUTE:
        return no_update
    try:
        if not may_view_dashboard(scope_for()):
            return None
        dashboard = fetch()
    except Exception:
        logger.exception("Failed to load the RTL dashboard")
        return ui.unavailable_panel()
    if dashboard.status is not DashboardStatus.DATA:
        return ui.unavailable_panel()
    return ui.dashboard_body(dashboard)


def register(app) -> None:
    @app.callback(Output(page.BODY_ID, "children"), Input("page-context", "data"))
    def populate_rtl_dashboard(context):
        return populate(context)
