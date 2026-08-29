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

from components.command_center.affected_locations import affected_locations_card
from components.command_center.electrical import electrical_conditions_card
from components.command_center.primitives import scope_indicator_text
from components.command_center.situation_summary import situation_summary_panels
from components.status_panels import error_panel
from services.command_center_service import get_command_center_snapshot
from services.device_scope import scope_from_session

logger = logging.getLogger(__name__)


def register(app) -> None:
    """Register Command Center callbacks on the Dash app."""

    @app.callback(
        Output("command-center-scope-indicator", "children"),
        Output("command-center-situation-summary", "children"),
        Output("command-center-exception-intelligence", "children"),
        Output("command-center-affected-locations", "children"),
        Output("command-center-error", "children"),
        Input("page-context", "data"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def populate_command_center(context, auth_data):
        """One snapshot, one render — the header and every card are served by
        the same fetch, so two parts of the page can never disagree about
        which RTLs are stale.
        """
        if not context or context.get("route") != "command_center":
            return no_update, no_update, no_update, no_update, no_update

        try:
            # Resolved once per render (ADR-004/ADR-008), same discipline
            # get_fleet_health's own docstring requires of every caller.
            scope = scope_from_session(auth_data)
            snapshot = get_command_center_snapshot(scope=scope)
            return (
                scope_indicator_text(snapshot.monitored_device_count),
                situation_summary_panels(snapshot),
                electrical_conditions_card(snapshot),
                affected_locations_card(snapshot),
                None,
            )
        except Exception:
            # Logged in full; the panel stays generic and never exposes
            # internals (AGENTS.md). The regions are cleared rather than
            # left showing "Loading…" forever — a stuck spinner reads as a
            # slow fleet, not a failed read.
            logger.exception("Failed to load Command Center snapshot")
            return no_update, [], [], [], error_panel()
