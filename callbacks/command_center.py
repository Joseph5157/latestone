"""Command Center callbacks — wire the service facade to the page.

Phase 3+4 (foundation and shell): one callback, populating only the header's
scope indicator. The six panel slots stay static "not yet available" cards
(components/command_center/primitives.py) until Phase 5 onward gives each
one its own callback and real data — this file grows with those phases, it
does not front-load them.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update

from components.command_center.primitives import scope_indicator_text
from components.status_panels import error_panel
from services.command_center_service import get_command_center_snapshot
from services.device_scope import scope_from_session

logger = logging.getLogger(__name__)


def register(app) -> None:
    """Register Command Center callbacks on the Dash app."""

    @app.callback(
        Output("command-center-scope-indicator", "children"),
        Output("command-center-error", "children"),
        Input("page-context", "data"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def populate_scope_indicator(context, auth_data):
        if not context or context.get("route") != "command_center":
            return no_update, no_update

        try:
            # Resolved once per render (ADR-004/ADR-008), same discipline
            # get_fleet_health's own docstring requires of every caller.
            scope = scope_from_session(auth_data)
            snapshot = get_command_center_snapshot(scope=scope)
            return scope_indicator_text(snapshot.monitored_device_count), None
        except Exception:
            logger.exception("Failed to load Command Center snapshot")
            return no_update, error_panel()
