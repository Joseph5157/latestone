"""The Fleet Overview - layout only, no queries (SATURDAY-REAL-FLEET-01).

Shows the registered client RTL directory (read-only client SQL Server).
Filled once per page load by `callbacks/fleet_overview.py`. No polling:
refreshing is a full reload of this route. The route stays `/plants`.
"""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.rtl_fleet import FILTER_ALL, SCOPE_NOTE
from routes import FLEET_OVERVIEW_PATH

STATS_ID = "fleet-overview-stats"
REFRESHED_ID = "fleet-overview-refreshed"
ERROR_ID = "fleet-overview-error"
LIST_ID = "fleet-overview-list"
FILTER_ID = "fleet-overview-filter"


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--fleet-overview",
        children=[
            app_header(breadcrumb_children=breadcrumb([("Fleet", None)])),
            html.H1("Fleet Overview"),
            html.P("Registered RTLs and their latest recorded temperature.", className="page__subtitle"),
            html.Div(className="fleet-refresh-context", children=[
                html.P(id=REFRESHED_ID, className="page__meta"),
                dcc.Link("Refresh", href=FLEET_OVERVIEW_PATH, refresh=True,
                         className="fleet-refresh-context__action"),
            ]),
            html.Div(id=STATS_ID),
            html.P(SCOPE_NOTE, className="fleet-overview-limits"),
            html.Div(id=ERROR_ID, className="listing-error"),
            html.Div(className="fleet-overview-toolbar", children=[
                dcc.RadioItems(id=FILTER_ID, options=[], value=FILTER_ALL, inline=True,
                               className="fleet-overview-chips",
                               labelClassName="fleet-overview-chip-option"),
            ]),
            html.Div(id=LIST_ID, children=[
                html.P("Loading registered RTLs…", className="fleet-overview-empty"),
            ]),
        ],
    )
