"""The redesigned Command Center (CC-NEW-1) — layout only, no queries.

"What needs my attention now?" for Administrators and Technicians
(redesign D1, D9). Filled by `callbacks/command_center_new.py` from one
`attention_service` snapshot per poll.

Reuses the old page's theme ids on purpose: its theme callbacks only touch
theme elements, so they serve this page unchanged, and the two pages are
never mounted together. Refresh ids are this page's own — the old refresh
ids are outputs of the old page's populate callback.
"""
from __future__ import annotations

from dash import dcc, html

from components.command_center import refresh, theme
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


def _loading(what: str) -> html.P:
    return html.P(f"Loading {what}…", className="command-center__loading")


def layout() -> html.Div:
    return html.Div(
        id=theme.ROOT_ID,
        # The theme callback REPLACES this className on every theme apply,
        # so this page's own class lives on the inner wrapper below.
        className=theme.root_class_name(theme.DEFAULT_THEME),
        children=[html.Div(className="attention-page", children=[
            dcc.Store(id=theme.STORE_ID, storage_type="session"),
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
                            theme.theme_toggle(theme.DEFAULT_THEME),
                        ],
                    ),
                ],
            ),
            html.Div(id=ERROR_ID, className="listing-error"),
            dcc.Store(id=ACK_STORE_ID, storage_type="memory"),
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
