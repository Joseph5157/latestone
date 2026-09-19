"""The redesigned Fleet Overview's one callback (FO-NEW-1).

One page load = one scope resolution (ADR-004) = one
`fleet_overview_service` snapshot = every output. A failed read shows the
shared error panel instead of an empty list, so an unreachable database never
reads as "no plants".
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from dash import Input, Output, no_update

from components import fleet_overview as ui
from components.status_panels import error_panel
from pages import plants_overview_new as page
from services.device_scope import current_device_scope
from services.fleet_overview_service import get_fleet_overview

logger = logging.getLogger(__name__)

ROUTE = "overview_new"
OUTPUTS = 5  # summary, refreshed, limits, plants, error


def populate(context, *, fetch=get_fleet_overview, scope_for=current_device_scope):
    """Body of the callback, testable without a Dash runtime."""
    if not context or context.get("route") != ROUTE:
        return (no_update,) * OUTPUTS
    try:
        now = datetime.now(timezone.utc)
        view = fetch(scope_for(), now=now)
    except Exception:
        logger.exception("Failed to load the Fleet Overview")
        return None, None, None, [], error_panel()
    return (
        ui.summary_line(view),
        f"Updated {now.strftime('%d %b %Y %H:%M UTC')}",
        ui.limits_line(view.limits),
        ui.plant_list(view),
        None,
    )


def register(app) -> None:
    @app.callback(
        Output(page.SUMMARY_ID, "children"),
        Output(page.REFRESHED_ID, "children"),
        Output(page.LIMITS_ID, "children"),
        Output(page.PLANTS_ID, "children"),
        Output(page.ERROR_ID, "children"),
        Input("page-context", "data"),
    )
    def populate_fleet_overview(context):
        return populate(context)
