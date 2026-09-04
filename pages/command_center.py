"""Command Center page — layout only, no queries.

Phase 3+4 (foundation and shell, docs/context/CC1_ROADMAP.md): the six
named panel slots exist and render an honest "not built yet" state; only
the header's scope indicator carries real data, filled in post-mount by
callbacks/command_center.py (matches pages/report_center.py's and
pages/notifications.py's own layout-then-callback convention). Fresh
presentation throughout — no imports from Fleet Overview components
(ADR-008).
"""
from __future__ import annotations

from dash import dcc, html

from components.command_center import refresh, theme

#: Situation Summary (Phase 5) is live: an empty region the callback fills
#: with the four real cards. It sits in its own full-width row above the
#: remaining slots — the operator's first read is the fleet's state, and a
#: compact four-across row is what makes that one glance.
SITUATION_SUMMARY_ID = "command-center-situation-summary"

#: Exception Intelligence (Phase 6) is live: the slot now holds the
#: Electrical Conditions card. The id is unchanged from Phase 4 so the
#: shell's DOM contract stays stable across phases; only its contents
#: graduated from placeholder to real.
ELECTRICAL_CONDITIONS_ID = "command-center-exception-intelligence"

#: Affected Locations (Phase 7) is live: the ranked plant bar view.
#: Same pattern as the two slots before it — the Phase 4 id is kept so
#: the shell's DOM contract stays stable while its contents graduate.
AFFECTED_LOCATIONS_ID = "command-center-affected-locations"

#: Selected Location (Phase 8). Id unchanged from Phase 4.
SELECTED_LOCATION_ID = "command-center-selected-location"

#: Recent Operational Events (Phase 9). Id unchanged from Phase 4.
RECENT_EVENTS_ID = "command-center-recent-events"

#: Priority Investigation (Phase 10) — the last Phase 4 slot to graduate.
#: With this one live there are no placeholder panels left, so
#: `panel_not_yet_built` is no longer imported here; it stays in primitives
#: for the next surface that needs an honest not-built-yet state.
PRIORITY_INVESTIGATION_ID = "command-center-priority-investigation"


def layout() -> html.Div:
    return html.Div(
        # The theme class rides beside the route class on ONE element, and
        # `assets/app.css` reaches the sidebar and utility chrome from here
        # via `:has()` — the same hook the fixed cockpit already uses. No
        # shell file knows a theme exists (ADR-006, amended).
        id=theme.ROOT_ID,
        className=theme.root_class_name(theme.DEFAULT_THEME),
        children=[
            # No app_header here, unlike every other page. The Eskom/
            # Powerplant brand bar and its breadcrumb restate what the
            # sidebar already shows, and in a fixed-height cockpit that
            # strip costs ~60px of the panel budget to say nothing new.
            # Sign-out is not lost with it: Logout now lives in the
            # globally-mounted sidebar (components/app_sidebar.py).
            # Session-scoped, the lifetime ADR-006 named and the one
            # `auth-store` already uses. Not localStorage: the choice is a
            # property of this shift at this console, not of the machine.
            # NO `data=` HERE, deliberately. Dash re-applies a Store's
            # declared initial data every time the component MOUNTS, and this
            # page remounts on every in-app navigation — so declaring a
            # default overwrote the operator's stored choice each time they
            # selected a Plant, silently snapping the appearance back to
            # dark. Omitting it lets the persisted session value load.
            # `apply_theme` already reads a missing value as DEFAULT_THEME,
            # so a genuinely first visit still opens dark.
            dcc.Store(id=theme.STORE_ID, storage_type="session"),
            # Page-owned, so leaving the route destroys it (ADR-005). There
            # is no app-wide interval and adding one would change Fleet
            # Overview's deliberately-tested absence of refresh.
            refresh.refresh_interval(),
            refresh.refresh_store(),
            html.Div(
                className="command-center__titlebar",
                children=[
                    html.Div(
                        className="command-center__titlebar-text",
                        children=[
                            html.H1("Command Center"),
                            html.P(
                                "Exception-first operational view across the "
                                "monitored fleet.",
                                className="page__subtitle",
                            ),
                            html.Div(
                                id="command-center-scope-indicator",
                                className="command-center__scope-indicator",
                            ),
                        ],
                    ),
                    html.Div(
                        className="command-center__titlebar-controls",
                        children=[
                            html.Div(
                                id=refresh.STATUS_ID,
                                className="command-center__refresh-slot",
                            ),
                            refresh.manual_refresh_button(),
                            theme.theme_toggle(theme.DEFAULT_THEME),
                        ],
                    ),
                ],
            ),
            html.Div(id="command-center-error", className="listing-error"),
            html.Div(
                id=SITUATION_SUMMARY_ID,
                className="command-center__summary-row",
                children=[
                    html.P(
                        "Loading situation summary…",
                        className="command-center__loading",
                    )
                ],
            ),
            html.Div(
                className="command-center__panels",
                children=[
                    html.Div(
                        id=ELECTRICAL_CONDITIONS_ID,
                        children=[
                            html.P(
                                "Loading electrical conditions…",
                                className="command-center__loading",
                            )
                        ],
                    ),
                    html.Div(
                        id=AFFECTED_LOCATIONS_ID,
                        className="command-center__panel--wide",
                        children=[
                            html.P(
                                "Loading affected locations…",
                                className="command-center__loading",
                            )
                        ],
                    ),
                    html.Div(
                        id=SELECTED_LOCATION_ID,
                        children=[
                            html.P(
                                "Loading selected location…",
                                className="command-center__loading",
                            )
                        ],
                    ),
                    html.Div(
                        id=RECENT_EVENTS_ID,
                        children=[
                            html.P(
                                "Loading recent events…",
                                className="command-center__loading",
                            )
                        ],
                    ),
                    html.Div(
                        id=PRIORITY_INVESTIGATION_ID,
                        children=[
                            html.P(
                                "Loading priority investigation…",
                                className="command-center__loading",
                            )
                        ],
                    ),
                ],
            ),
        ],
    )
