"""The Fleet Overview (FO-NEW-1) — layout only, no queries.

"Where is everything and how hot is it?" for every role (redesign D1, D6).
Filled once per page load by `callbacks/fleet_overview.py`. No polling:
a poll would re-render the list and close every plant the reader opened, so
refreshing is a full reload of this route.
"""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from routes import FLEET_OVERVIEW_PATH

SUMMARY_ID = "fleet-overview-summary"
REFRESHED_ID = "fleet-overview-refreshed"
LIMITS_ID = "fleet-overview-limits"
ERROR_ID = "fleet-overview-error"
PLANTS_ID = "fleet-overview-plants"


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--fleet-overview",
        children=[
            app_header(breadcrumb_children=breadcrumb([("Fleet", None)])),
            html.H1("Fleet Overview"),
            html.P("Where everything is and how hot it is.", className="page__subtitle"),
            html.Div(className="fleet-refresh-context", children=[
                html.P(id=SUMMARY_ID, className="page__meta"),
                html.P(id=REFRESHED_ID, className="page__meta"),
                dcc.Link("Refresh", href=FLEET_OVERVIEW_PATH, refresh=True,
                         className="fleet-refresh-context__action"),
            ]),
            html.Div(id=LIMITS_ID),
            html.Div(id=ERROR_ID, className="listing-error"),
            html.Div(id=PLANTS_ID, children=[
                html.P("Loading plants…", className="fleet-overview-empty"),
            ]),
        ],
    )
