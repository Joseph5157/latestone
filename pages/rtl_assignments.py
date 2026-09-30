"""Technician Assignments - layout only, no queries (ADR-032).

Administrator-only management of which Technician holds which client RTL:
the current assignment list, the Unassigned RTLs pool, assign, reassign and
history. Filled by ``callbacks/rtl_assignments.py``. Every id below is a fixed,
always-present element, so no callback targets something that may not exist.
"""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb

STORE_ID = "rtl-assign-store"  # snapshot rows for filtering (no reads per filter)
VERSION_ID = "rtl-assign-version"  # bumped after a change so the list reloads
SELECTED_ID = "rtl-assign-selected"  # {"uid", "mode", "assignment_id"}
STATS_ID = "rtl-assign-stats"
ERROR_ID = "rtl-assign-error"
VIEW_ID = "rtl-assign-view"
TECH_FILTER_ID = "rtl-assign-tech-filter"
UID_SEARCH_ID = "rtl-assign-uid-search"
LIST_ID = "rtl-assign-list"
PANEL_ID = "rtl-assign-panel"
PANEL_TITLE_ID = "rtl-assign-panel-title"
PANEL_NOTE_ID = "rtl-assign-panel-note"
TARGET_ID = "rtl-assign-target"
CONFIRM_ID = "rtl-assign-confirm"
CANCEL_ID = "rtl-assign-cancel"
MESSAGE_ID = "rtl-assign-message"
HISTORY_ID = "rtl-assign-history"
PICK_TYPE = "rtl-assign-pick"

HIDDEN_STYLE = {"display": "none"}
VISIBLE_STYLE = {"display": "block"}

VIEW_OPTIONS = [
    {"label": "All RTLs", "value": "all"},
    {"label": "Assigned", "value": "assigned"},
    {"label": "Unassigned RTLs", "value": "unassigned"},
]


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--rtl-assignments",
        children=[
            app_header(breadcrumb_children=breadcrumb([("Technician Assignments", None)])),
            html.H1("Technician Assignments"),
            html.P(
                "Each RTL has at most one Technician at a time. A Technician sees only the "
                "RTLs assigned to them. RTLs with no Technician are the Unassigned RTLs pool.",
                className="page__subtitle",
            ),
            dcc.Store(id=STORE_ID),
            dcc.Store(id=VERSION_ID, data=0),
            dcc.Store(id=SELECTED_ID),
            html.Div(id=STATS_ID),
            html.Div(id=ERROR_ID, className="listing-error"),
            html.Div(className="fleet-overview-toolbar", children=[
                dcc.RadioItems(id=VIEW_ID, options=VIEW_OPTIONS, value="all", inline=True,
                               className="fleet-overview-chips",
                               labelClassName="fleet-overview-chip-option"),
                dcc.Dropdown(id=TECH_FILTER_ID, options=[], value=None, clearable=True,
                             placeholder="Any Technician", className="rtl-assign-filter"),
                dcc.Input(id=UID_SEARCH_ID, type="text", value="", debounce=False,
                          placeholder="Search RTL UID", className="rtl-assign-search"),
            ]),
            html.Section(id=PANEL_ID, style=HIDDEN_STYLE, className="rtl-summary-panel", children=[
                html.H2(id=PANEL_TITLE_ID, className="rtl-detail-section__title"),
                html.P(id=PANEL_NOTE_ID, className="fleet-overview-limits"),
                dcc.Dropdown(id=TARGET_ID, options=[], value=None, clearable=False,
                             placeholder="Choose a Technician", className="rtl-assign-target"),
                html.Div(className="rtl-assign-actions", children=[
                    html.Button("Confirm", id=CONFIRM_ID, type="button", n_clicks=0,
                                className="btn btn--primary"),
                    html.Button("Close", id=CANCEL_ID, type="button", n_clicks=0,
                                className="btn"),
                ]),
                html.Div(id=MESSAGE_ID, role="status", className="rtl-assign-message"),
                html.Div(id=HISTORY_ID),
            ]),
            html.Div(id=LIST_ID, children=[
                html.P("Loading assignments…", className="fleet-overview-empty"),
            ]),
        ],
    )
