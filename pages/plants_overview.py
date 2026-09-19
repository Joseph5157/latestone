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
from components.fleet_overview import SORT_OPTIONS
from routes import FLEET_OVERVIEW_PATH
from services.fleet_overview_service import FILTER_ALL, SORT_NAME

STATS_ID = "fleet-overview-stats"
REFRESHED_ID = "fleet-overview-refreshed"
LIMITS_ID = "fleet-overview-limits"
ERROR_ID = "fleet-overview-error"
PLANTS_ID = "fleet-overview-plants"
FILTER_ID = "fleet-overview-filter"
SORT_ID = "fleet-overview-sort"


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--fleet-overview",
        children=[
            app_header(breadcrumb_children=breadcrumb([("Fleet", None)])),
            html.H1("Fleet Overview"),
            html.P("Where everything is and how hot it is.", className="page__subtitle"),
            html.Div(className="fleet-refresh-context", children=[
                html.P(id=REFRESHED_ID, className="page__meta"),
                dcc.Link("Refresh", href=FLEET_OVERVIEW_PATH, refresh=True,
                         className="fleet-refresh-context__action"),
            ]),
            # STATS-CARDS-1: four temperature stat cards, filled by the callback.
            html.Div(id=STATS_ID),
            html.Div(id=LIMITS_ID),
            html.Div(id=ERROR_ID, className="listing-error"),
            # POLISH-1: options (with counts) are written by the callback from
            # the same snapshot as the list below.
            html.Div(className="fleet-overview-toolbar", children=[
                dcc.RadioItems(id=FILTER_ID, options=[], value=FILTER_ALL, inline=True,
                               className="fleet-overview-chips",
                               labelClassName="fleet-overview-chip-option"),
                html.Div(className="fleet-overview-sort", children=[
                    html.Span("Sort", className="fleet-overview-sort__label"),
                    dcc.RadioItems(id=SORT_ID, options=SORT_OPTIONS, value=SORT_NAME,
                                   inline=True, className="fleet-overview-chips",
                                   labelClassName="fleet-overview-chip-option"),
                ]),
            ]),
            html.Div(id=PLANTS_ID, children=[
                html.P("Loading plants…", className="fleet-overview-empty"),
            ]),
        ],
    )
