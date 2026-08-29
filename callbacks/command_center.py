"""Command Center callbacks — wire the service facade to the page.

Phase 3+4 (foundation and shell): one callback, populating only the header's
scope indicator. The six panel slots stay static "not yet available" cards
(components/command_center/primitives.py) until Phase 5 onward gives each
one its own callback and real data — this file grows with those phases, it
does not front-load them.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, html, no_update

from components.command_center.affected_locations import (
    affected_locations_card,
    ranked_locations_list,
)
from components.command_center.electrical import electrical_conditions_card
from components.command_center.primitives import scope_indicator_text
from components.command_center.selected_location import selected_location_card
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
        Output("command-center-selected-location", "children"),
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
            return (no_update,) * 6

        try:
            # Resolved once per render (ADR-004/ADR-008), same discipline
            # get_fleet_health's own docstring requires of every caller.
            scope = scope_from_session(auth_data)
            snapshot = get_command_center_snapshot(
                scope=scope, selected_plant_id=context.get("plant_id")
            )
            return (
                scope_indicator_text(snapshot.monitored_device_count),
                situation_summary_panels(snapshot),
                electrical_conditions_card(snapshot),
                affected_locations_card(snapshot),
                selected_location_card(snapshot),
                None,
            )
        except Exception:
            # Logged in full; the panel stays generic and never exposes
            # internals (AGENTS.md). The regions are cleared rather than
            # left showing "Loading…" forever — a stuck spinner reads as a
            # slow fleet, not a failed read.
            logger.exception("Failed to load Command Center snapshot")
            return no_update, [], [], [], [], error_panel()

    @app.callback(
        Output("command-center-locations-list", "children"),
        Output("command-center-locations-summary", "children"),
        Output("command-center-locations-error", "children"),
        Input("page-context", "data"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def populate_locations_full_view(context, auth_data):
        """The same ranked data as the panel, without the height cap.

        Reads through the same facade and the same row renderer, so the
        full view can never disagree with the panel it was opened from.
        """
        if not context or context.get("route") != "command_center_locations":
            return no_update, no_update, no_update

        try:
            scope = scope_from_session(auth_data)
            snapshot = get_command_center_snapshot(scope=scope)
            ranked = [row for row in snapshot.affected_locations if row.affected_rtls]

            if not ranked:
                message = (
                    "No RTLs require attention in your current access scope."
                    if snapshot.affected_locations
                    else "No monitored RTLs in your current access scope."
                )
                return (
                    [html.P(message, className="command-center__empty-note")],
                    "",
                    None,
                )

            total = len(snapshot.affected_locations)
            noun = "plant" if total == 1 else "plants"
            return (
                ranked_locations_list(ranked),
                f"{len(ranked)} of {total} {noun} affected",
                None,
            )
        except Exception:
            logger.exception("Failed to load the full affected-locations view")
            return [], "", error_panel()
