"""Historical Events - layout only, no queries (HISTORICAL-EVENTS-01).

Recorded events from the client event logs, at ``/events``. Filled by
``callbacks/historical_events.py``: the date window is set once per page load
from the newest recorded event, then each filter change is one bounded read.
No polling.
"""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from services.rtl_events_service import EventType

START_ID = "historical-events-dates"
TYPE_ID = "historical-events-type"
UID_ID = "historical-events-uid"
PREV_ID = "historical-events-prev"
NEXT_ID = "historical-events-next"
PAGE_STORE_ID = "historical-events-page"
BODY_ID = "historical-events-body"
ALL_TYPES = "all"


def type_options() -> list[dict]:
    return [{"label": "All events", "value": ALL_TYPES}] + [
        {"label": t.label, "value": t.value} for t in EventType]


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--historical-events",
        children=[
            app_header(breadcrumb_children=breadcrumb([("Historical Events", None)])),
            html.H1("Historical Events"),
            html.P("Events recorded by the client RTLs: High Temperature, Sensor Error, "
                   "Battery Low and Powerdown.", className="page__subtitle"),
            dcc.Store(id=PAGE_STORE_ID, data=0),
            html.Div(className="network-filters", children=[
                html.Div([
                    html.Label("Event type", htmlFor=TYPE_ID),
                    dcc.Dropdown(id=TYPE_ID, options=type_options(), value=ALL_TYPES, clearable=False),
                ]),
                html.Div([
                    html.Label("Date range", htmlFor=START_ID),
                    dcc.DatePickerRange(id=START_ID, display_format="YYYY-MM-DD",
                                        start_date=None, end_date=None, clearable=False),
                ]),
                html.Div([
                    html.Label("RTL UID", htmlFor=UID_ID),
                    dcc.Input(id=UID_ID, type="text", debounce=True, value="", placeholder="e.g. 29042",
                              maxLength=10, className="events-uid-input"),
                ]),
            ]),
            html.Div(id=BODY_ID, children=[html.P("Loading events…", className="fleet-overview-empty")]),
            html.Div(className="events-pager", children=[
                html.Button("Previous", id=PREV_ID, n_clicks=0, type="button"),
                html.Button("Next", id=NEXT_ID, n_clicks=0, type="button"),
            ]),
        ],
    )
