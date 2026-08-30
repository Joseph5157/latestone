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

from dash import html

from components.command_center.primitives import panel_not_yet_built

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

#: (component id, panel title) — the slots still awaiting their own phase
#: (docs/context/CC1_ROADMAP.md Phase 10). Each renders an honest
#: not-built-yet card until then.
_PANEL_SLOTS: tuple[tuple[str, str], ...] = (
    ("command-center-priority-investigation", "Priority Investigation"),
)


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--command-center",
        children=[
            # No app_header here, unlike every other page. The Eskom/
            # Powerplant brand bar and its breadcrumb restate what the
            # sidebar already shows, and in a fixed-height cockpit that
            # strip costs ~60px of the panel budget to say nothing new.
            # Sign-out is not lost with it: Logout now lives in the
            # globally-mounted sidebar (components/app_sidebar.py).
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
                ],
            ),
            html.Div(id="command-center-error"),
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
                    *(
                        html.Div(id=slot_id, children=[panel_not_yet_built(title)])
                        for slot_id, title in _PANEL_SLOTS
                    ),
                ],
            ),
        ],
    )
