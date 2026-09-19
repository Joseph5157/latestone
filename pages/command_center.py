"""The Command Center (CC-NEW-1) — layout only, no queries.

"What needs my attention now?" for Administrators and Technicians
(redesign D1, D9). Filled by `callbacks/command_center.py` from one
`attention_service` snapshot per poll.

The Dark / Light choice is app-wide (ADR-025): its toggle is in the
sidebar and its class on `app-root`.
"""
from __future__ import annotations

from dash import dcc, html

from components.command_center import refresh
from components.device_manage_drawer import device_manage_drawer

INTERVAL_ID = "attention-refresh-interval"
STORE_ID = "attention-refresh-store"
REFRESH_STATUS_ID = "attention-refresh-status"
REFRESH_NOW_ID = "attention-refresh-now"
SCOPE_ID = "attention-scope"
ERROR_ID = "attention-error"
STATUS_SLOT_ID = "attention-status-slot"
PROBLEMS_ID = "attention-problems-slot"
HOTTEST_ID = "attention-hottest-slot"
ACTIVITY_ID = "attention-activity-slot"
TREND_ID = "attention-trend-slot"
#: CC-ACTIONS-1: a result notice for Acknowledge, and a store the populate
#: callback listens to so an acknowledgement refreshes the list at once.
ACTION_RESULT_ID = "attention-action-result"
ACK_STORE_ID = "attention-ack-store"
ROOT_ID = "command-center-root"
ROOT_CLASS = "page page--monitoring page--command-center"
#: CLICK-FILTER-1: the severity tone the problem list is narrowed to, or None.
SEVERITY_STORE_ID = "attention-severity-store"


def _loading(what: str) -> html.P:
    return html.P(f"Loading {what}…", className="command-center__loading")


def layout() -> html.Div:
    return html.Div(
        id=ROOT_ID,
        # The appearance is app-wide now (ADR-025): the theme class lives on
        # `app-root`, not here.
        className=ROOT_CLASS,
        children=[html.Div(className="attention-page", children=[
            dcc.Interval(id=INTERVAL_ID, interval=refresh.interval_ms(), n_intervals=0),
            dcc.Store(id=STORE_ID, data={"last_success_at": None, "failed": False},
                      storage_type="memory"),
            html.Div(
                className="command-center__titlebar",
                children=[
                    html.Div(
                        className="command-center__titlebar-text",
                        children=[
                            html.H1("Command Center"),
                            html.P("What needs attention now.", className="page__subtitle"),
                            html.Div(id=SCOPE_ID, className="command-center__scope-indicator"),
                        ],
                    ),
                    html.Div(
                        className="command-center__titlebar-controls",
                        children=[
                            html.Div(id=REFRESH_STATUS_ID, className="command-center__refresh-slot"),
                            html.Button("Refresh now", id=REFRESH_NOW_ID, n_clicks=0,
                                        type="button",
                                        className="command-center__refresh-now"),
                        ],
                    ),
                ],
            ),
            html.Div(id=ERROR_ID, className="listing-error"),
            dcc.Store(id=ACK_STORE_ID, storage_type="memory"),
            dcc.Store(id=SEVERITY_STORE_ID, data=None, storage_type="memory"),
            html.Div(id=ACTION_RESULT_ID, className="attention-notice", **{"aria-live": "polite"}),
            html.Div(id=STATUS_SLOT_ID, children=[_loading("status")]),
            html.Div(
                className="attention-grid",
                children=[
                    html.Div(id=PROBLEMS_ID, className="attention-grid__main",
                             children=[_loading("problems")]),
                    html.Div(className="attention-grid__side", children=[
                        html.Div(id=HOTTEST_ID, children=[_loading("temperatures")]),
                        html.Div(id=TREND_ID, children=[_loading("alarm trend")]),
                        html.Div(id=ACTIVITY_ID, children=[_loading("activity")]),
                    ]),
                ],
            ),
            # The SAME drawer Device Management and a Technician's Devices
            # page open (ADR-016); its confirm callbacks re-check authority.
            device_manage_drawer(),
        ])],
    )
