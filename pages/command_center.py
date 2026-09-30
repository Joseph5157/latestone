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
from components.status_colors import colour_key

INTERVAL_ID = "attention-refresh-interval"
STORE_ID = "attention-refresh-store"
REFRESH_STATUS_ID = "attention-refresh-status"
REFRESH_NOW_ID = "attention-refresh-now"
#: CC-HEADER-TRIM-1: no SCOPE_ID. The scope indicator showed
#: `snapshot.total_rtls` — the same integer the Working severity card already
#: renders as its denominator, for every role. ADR-004 forbids the indicator
#: becoming a *selector*; it never required one to exist.
ERROR_ID = "attention-error"
STATUS_SLOT_ID = "attention-status-slot"
PROBLEMS_ID = "attention-problems-slot"
#: CC-GAUGES-1 (ADR-028): working half-arc + problem donut, above the list.
GLANCE_ID = "attention-glance-slot"
HOTTEST_ID = "attention-hottest-slot"
ACTIVITY_ID = "attention-activity-slot"
TREND_ID = "attention-trend-slot"
#: CC-ACTIONS-1: a result notice for Acknowledge, and a store the populate
#: callback listens to so an acknowledgement refreshes the list at once.
ACTION_RESULT_ID = "attention-action-result"
ACK_STORE_ID = "attention-ack-store"
RTL_SUMMARY_ID = "command-center-rtl-summary"
ROOT_ID = "command-center-root"
ROOT_CLASS = "page page--monitoring page--command-center"
#: CLICK-FILTER-1: the severity tone the problem list is narrowed to, or None.
SEVERITY_STORE_ID = "attention-severity-store"
#: PROBLEM-GROUPS-2: the problem kinds folded away, kept for the browser tab.
FOLDED_STORE_ID = "attention-folded-store"
#: CC-FILTER-FAST-1: the element whose `attention-filter--<tone>` class
#: applies the severity filter in the browser (assets/command_center.js).
FILTER_ROOT_ID = "attention-filter-root"
#: CC-FILTER-FAST-1: real clicks only ({id, n, at}), written in the browser;
#: re-render "clicks" (n_clicks 0) never reach the server.
SEVERITY_CLICK_ID = "attention-severity-click"
ACK_CLICK_ID = "attention-ack-click"
MANAGE_CLICK_ID = "attention-manage-click"
FOLD_CLICK_ID = "attention-fold-click"


def _loading(what: str) -> html.P:
    return html.P(f"Loading {what}…", className="command-center__loading")


def layout() -> html.Div:
    return html.Div(
        id=ROOT_ID,
        # The appearance is app-wide now (ADR-025): the theme class lives on
        # `app-root`, not here.
        className=ROOT_CLASS,
        children=[html.Div(id=FILTER_ROOT_ID, className="attention-page", children=[
            dcc.Interval(id=INTERVAL_ID, interval=refresh.interval_ms(), n_intervals=0),
            dcc.Store(id=STORE_ID, data={"last_success_at": None, "failed": False},
                      storage_type="memory"),
            html.Div(
                className="command-center__titlebar",
                children=[
                    html.Div(
                        className="command-center__titlebar-text",
                        children=[html.H1("Command Center")],
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
            dcc.Store(id=FOLDED_STORE_ID, data=[], storage_type="session"),
            *(dcc.Store(id=click_id, storage_type="memory")
              for click_id in (SEVERITY_CLICK_ID, ACK_CLICK_ID, MANAGE_CLICK_ID, FOLD_CLICK_ID)),
            html.Div(id=ACTION_RESULT_ID, className="attention-notice", **{"aria-live": "polite"}),
            # RTL-NETWORK-USE-01: real client RTL facts, filled by
            # callbacks/rtl_summary.py; stays empty for roles not permitted.
            html.Div(id=RTL_SUMMARY_ID),
            html.Div(id=STATUS_SLOT_ID, children=[_loading("status")]),
            colour_key(),
            html.Div(
                className="attention-grid",
                children=[
                    html.Div(className="attention-grid__main", children=[
                        html.Div(id=GLANCE_ID, children=[_loading("fleet summary")]),
                        html.Div(id=PROBLEMS_ID, children=[_loading("problems")]),
                    ]),
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
