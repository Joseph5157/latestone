"""Affected Locations, in full — layout only, no queries.

The Command Center panel is deliberately bounded (a fixed cockpit has a
fixed vertical budget), so comparing rank 3 against rank 27 means scrolling
a small pane. This is the same ranked list without that constraint.

A route, not a modal. The ask was for a full, resizable view, and a modal
is precisely what cannot be one — it floats inside the viewport, and making
it resizable means hand-built drag handles. A page already is full-size and
resizable, and is bookmarkable and shareable besides. It also needs none of
the focus-trap / scroll-lock / ESC machinery a correct modal requires, which
this codebase has nowhere else.

Deliberately NOT the fixed cockpit: `page--command-center` is what turns on
that layout, and this page does not carry it. An unbounded list is the whole
point, so this one scrolls like any other page.
"""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb

#: Back to the cockpit. Matches routes.parse_pathname's "command_center".
COMMAND_CENTER_PATH = "/command-center"


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--command-center-locations",
        children=[
            # This page DOES render app_header, unlike the cockpit: the
            # breadcrumb is doing real work here (it is the way back), and
            # there is no fixed vertical budget for it to compete with.
            app_header(
                breadcrumb_children=breadcrumb(
                    [("Command Center", COMMAND_CENTER_PATH), ("Affected Locations", None)]
                ),
            ),
            html.H1("Affected Locations"),
            html.P(
                "Every plant with RTLs requiring attention, worst first.",
                className="page__subtitle",
            ),
            html.Div(
                id="command-center-locations-summary",
                className="command-center__scope-indicator",
            ),
            html.Div(id="command-center-locations-error", className="listing-error"),
            html.Div(
                id="command-center-locations-list",
                className="command-center__locations-full",
                children=[
                    html.P(
                        "Loading affected locations…",
                        className="command-center__loading",
                    )
                ],
            ),
            dcc.Link(
                "← Back to Command Center",
                href=COMMAND_CENTER_PATH,
                className="command-center__view-all",
            ),
        ],
    )
