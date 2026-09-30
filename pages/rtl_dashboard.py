"""Dashboard - layout only, no queries (FACTUAL-DASHBOARD-01).

The factual client RTL dashboard, served at the Administrator's landing
address. Filled once per page load by ``callbacks/rtl_dashboard.py``; no
polling, no synthetic PostgreSQL content.
"""
from __future__ import annotations

from dash import html

BODY_ID = "rtl-dashboard-body"
ROOT_CLASS = "page page--monitoring page--rtl-dashboard"


def layout() -> html.Div:
    return html.Div(className=ROOT_CLASS, children=[
        html.H1("Dashboard"),
        html.P("Registered client RTLs, their current network mapping and the temperature "
               "data on record.", className="page__subtitle"),
        html.Div(id=BODY_ID, children=[html.P("Loading…", className="command-center__loading")]),
    ])
