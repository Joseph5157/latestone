"""Command Center callbacks — wire the service facade to the page.

Phase 3+4 (foundation and shell): one callback, populating only the header's
scope indicator. The six panel slots stay static "not yet available" cards
(components/command_center/primitives.py) until Phase 5 onward gives each
one its own callback and real data — this file grows with those phases, it
does not front-load them.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from dash import Input, Output, State, ctx, html, no_update

from components.command_center.affected_locations import (
    affected_locations_card,
    ranked_locations_list,
)
from components.command_center.electrical import electrical_conditions_card
from components.command_center.primitives import scope_indicator_text
from components.command_center import refresh, theme
from components.command_center.priority import priority_investigation_card
from components.command_center.recent_events import recent_events_card
from components.command_center.selected_location import selected_location_card
from components.command_center.situation_summary import situation_summary_panels
from components.status_panels import error_panel
from services.auth_service import current_identity
from services.authorization import ADMINISTRATOR
from services.command_center_service import get_command_center_snapshot
from services.device_scope import current_device_scope

logger = logging.getLogger(__name__)


#: The outputs of the refresh callback that render DATA (scope indicator plus
#: the six panels). Counted rather than spelled out so a future panel cannot
#: be added to the callback while the failure path keeps clearing only the
#: ones that existed when it was written.
PANEL_OUTPUT_COUNT = 7

#: Index of the generic error region within that callback's return tuple.
ERROR_OUTPUT_INDEX = 7

#: Panels + error + refresh status + refresh store.
OUTPUT_COUNT = 10


def _last_success(refresh_state):
    """When the last SUCCESSFUL snapshot landed, or None if none ever has.

    The None case is the whole reason this is a STORED fact rather than
    something read back off the page: a first load that fails and a refresh
    that fails look identical in the DOM, and they must not be handled the
    same way.
    """
    stamp = (refresh_state or {}).get("last_success_at")
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        # A malformed value is treated as "never succeeded" rather than
        # crashing the only callback that can recover the page.
        return None



def register(app) -> None:
    """Register Command Center callbacks on the Dash app."""

    @app.callback(
        Output("command-center-scope-indicator", "children"),
        Output("command-center-situation-summary", "children"),
        Output("command-center-exception-intelligence", "children"),
        Output("command-center-affected-locations", "children"),
        Output("command-center-selected-location", "children"),
        Output("command-center-recent-events", "children"),
        Output("command-center-priority-investigation", "children"),
        Output("command-center-error", "children"),
        Output(refresh.STATUS_ID, "children"),
        Output(refresh.STORE_ID, "data"),
        Input("page-context", "data"),
        Input(refresh.INTERVAL_ID, "n_intervals"),
        Input(refresh.MANUAL_ID, "n_clicks"),
        State("auth-store", "data"),
        State(refresh.STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def populate_command_center(context, _ticks, _manual, auth_data, refresh_state):
        """One snapshot, one render — the header and every card are served by
        the same fetch, so two parts of the page can never disagree about
        which RTLs are stale. That discipline is what makes polling safe:
        one interval tick is ONE snapshot assembly, not six panels each
        going to the database on their own (ADR-005 over ADR-008).

        The selected Plant is NOT re-derived here. It rides in
        `page-context` from the URL (`?plant=`), so a routine poll cannot
        reset the operator to the top-ranked plant - no callback owns the
        selection, so none can lose it.
        """
        if not context or context.get("route") != "command_center":
            return (no_update,) * OUTPUT_COUNT

        try:
            # Resolved once per render (ADR-004/ADR-008), same discipline
            # get_fleet_health's own docstring requires of every caller.
            scope = current_device_scope()
            # EVT-D5, applying the precedent this app already set in
            # callbacks/notifications.py: an unregistered UID belongs to no
            # device set, so scope alone cannot decide who may see the
            # quarantine rows. Only an administrator asks for them.
            user = current_identity()
            is_admin = user is not None and user.role == ADMINISTRATOR
            # One reference time, used for the fetch AND for the label, so
            # `Last updated` names the moment the DATA describes rather than
            # the moment the render happened to finish.
            fetched_at = datetime.now(timezone.utc)
            snapshot = get_command_center_snapshot(
                scope=scope,
                selected_plant_id=context.get("plant_id"),
                include_unregistered=is_admin,
                now=fetched_at,
            )
            return (
                scope_indicator_text(snapshot.monitored_device_count),
                situation_summary_panels(snapshot),
                electrical_conditions_card(snapshot),
                affected_locations_card(snapshot),
                selected_location_card(snapshot),
                # An events read that failed did NOT fail the snapshot — the
                # facade holds that boundary (ADR-008) and the card states
                # which of "nothing happened" / "could not look" it has.
                recent_events_card(snapshot),
                priority_investigation_card(snapshot),
                None,
                refresh.refresh_status(fetched_at, failed=False),
                # A success always clears a previous failure, so the banner
                # disappears on its own at the next good poll.
                {"last_success_at": fetched_at.isoformat(), "failed": False},
            )
        except Exception:
            # Logged in full; the UI stays generic and never exposes
            # internals (AGENTS.md).
            logger.exception("Failed to load Command Center snapshot")
            last_success = _last_success(refresh_state)

            if last_success is None:
                # FIRST LOAD. No last-good data exists, so there is nothing
                # for a stale-data banner to sit over. Clear the regions
                # rather than leave "Loading..." forever - a stuck spinner
                # reads as a slow fleet, not a failed read - and show the
                # ordinary error state.
                return (
                    no_update, [], [], [], [], [], [],
                    error_panel(),
                    refresh.refresh_status(None, failed=False),
                    {"last_success_at": None, "failed": True},
                )

            # A FAILED REFRESH over data that is still true. `no_update`
            # leaves every rendered panel exactly as it was: blanking them
            # would throw away a screen of correct information because one
            # query timed out, and an empty Needs Attention card reads as
            # "nothing is wrong" rather than "we could not look".
            #
            # `last_success_at` is deliberately NOT advanced. It names the
            # age of what is on screen, and moving it on a failed attempt
            # would claim freshness at the one moment that claim is false.
            return (no_update,) * PANEL_OUTPUT_COUNT + (
                no_update,
                refresh.refresh_status(last_success, failed=True),
                {"last_success_at": refresh_state["last_success_at"], "failed": True},
            )


    @app.callback(
        Output(theme.STORE_ID, "data"),
        Input(theme.TOGGLE_DARK_ID, "n_clicks"),
        Input(theme.TOGGLE_LIGHT_ID, "n_clicks"),
        prevent_initial_call=True,
    )
    def choose_theme(_dark_clicks, _light_clicks):
        """Which appearance the operator picked (ADR-006).

        Reads `ctx.triggered_id` rather than comparing click counts: counts
        drift the moment a button is re-rendered with `n_clicks=0`, and the
        question here is only ever "which one was pressed".
        """
        pressed = ctx.triggered_id
        if pressed == theme.TOGGLE_LIGHT_ID:
            return {"theme": theme.LIGHT}
        if pressed == theme.TOGGLE_DARK_ID:
            return {"theme": theme.DARK}
        return no_update

    @app.callback(
        Output(theme.ROOT_ID, "className"),
        Output(theme.TOGGLE_DARK_ID, "className"),
        Output(theme.TOGGLE_LIGHT_ID, "className"),
        Output(theme.TOGGLE_DARK_ID, "aria-pressed"),
        Output(theme.TOGGLE_LIGHT_ID, "aria-pressed"),
        Input(theme.STORE_ID, "data"),
    )
    def apply_theme(data):
        """One className swap re-themes the workspace AND the shell around
        it — the sidebar and utility chrome follow via `:has()` in the
        stylesheet, so nothing in the shell is touched (ADR-006, amended).

        Driven by the STORE rather than by the buttons, so the stored choice
        is re-applied whenever the page mounts. Without that, returning to
        `/command-center` in the same session would render the default while
        the store still said otherwise.
        """
        choice = (data or {}).get("theme", theme.DEFAULT_THEME)
        dark_class, dark_pressed = theme.option_state(theme.DARK, choice)
        light_class, light_pressed = theme.option_state(theme.LIGHT, choice)
        return (
            theme.root_class_name(choice),
            dark_class,
            light_class,
            dark_pressed,
            light_pressed,
        )

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
            scope = current_device_scope()
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
