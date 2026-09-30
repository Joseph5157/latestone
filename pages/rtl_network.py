"""Network - layout only, no queries (LATEST-NETWORK-CONTEXT-01).

The current network context of the registered client RTLs, at ``/rtls/network``:
Zone -> Sector -> CNC -> Feeder -> Transformer -> RTL. Read once per page load
by ``callbacks/rtl_network.py`` into a page store; every filter change is a
re-render of that snapshot. No polling: refreshing is a full reload.
"""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.rtl_network import LEVEL_LABELS, LEVEL_PLURALS, SCOPE_NOTE
from routes import FLEET_OVERVIEW_PATH
from services.rtl_network_service import LEVELS, SCOPE_ALL

STORE_ID = "rtl-network-data"
STATS_ID = "rtl-network-stats"
ERROR_ID = "rtl-network-error"
SCOPE_ID = "rtl-network-scope"
BREAKDOWN_ID = "rtl-network-breakdown"
LIST_ID = "rtl-network-list"


def filter_id(level: str) -> str:
    return f"rtl-network-filter-{level}"


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--rtl-network",
        children=[
            app_header(breadcrumb_children=breadcrumb([
                ("Registered RTLs", FLEET_OVERVIEW_PATH),
                ("Network", None),
            ])),
            html.H1("Network"),
            html.P("Where each registered RTL sits in the client's network, by its current "
                   "transformer mapping.", className="page__subtitle"),
            dcc.Store(id=STORE_ID),
            html.Div(id=STATS_ID),
            html.P(SCOPE_NOTE, className="fleet-overview-limits"),
            html.Div(id=ERROR_ID, className="listing-error"),
            dcc.RadioItems(id=SCOPE_ID, options=[], value=SCOPE_ALL, inline=True,
                           className="fleet-overview-chips",
                           labelClassName="fleet-overview-chip-option"),
            html.Div(className="network-filters", children=[
                html.Div([
                    html.Label(LEVEL_LABELS[level], htmlFor=filter_id(level)),
                    dcc.Dropdown(id=filter_id(level), options=[], value=None, clearable=True,
                                 placeholder=f"All {LEVEL_PLURALS[level]}"),
                ])
                for level in LEVELS
            ]),
            html.Div(id=BREAKDOWN_ID),
            html.Div(id=LIST_ID, children=[
                html.P("Loading the network…", className="fleet-overview-empty"),
            ]),
        ],
    )
