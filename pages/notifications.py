"""Notification Center page — layout only, no queries.

Notification categories are confirmed by the RTL Functional Specification
(§3, §11). Notification display is implemented (BR008 derivation plus
persisted device events); external delivery such as SMS/email is NOT
connected — the banner below states exactly that distinction, no more.
"""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.entity_table import entity_table
from config.notifications import all_categories

#: Per-row override: an unregistered UID has no device route, so its entity
#: cell must not borrow the clickable link styling (ENT-4 gate decision).
_UNREGISTERED_PLAIN_TEXT_STYLE = {
    "if": {
        "filter_query": '{entity_type} eq "Unregistered UID"',
        "column_id": "entity_label",
    },
    "color": "inherit",
    "textDecoration": "none",
    "cursor": "default",
    "whiteSpace": "nowrap",
}


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--notifications",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([("Notification Center", None)]),
            ),
            html.H1("Notification Center"),
            html.P(
                "Monitor formal business notifications and data freshness status.",
                className="page__subtitle",
            ),
            dcc.Store(id="notification-refresh", data={"event_id": None}),
            # Honesty banner. The distinction is display vs delivery: the rows
            # in this table are real (BR008 + persisted device events), but
            # nothing is sent anywhere.
            html.Div(
                className="status-panel status-panel--inactive",
                children=[
                    html.Strong("Prototype. "),
                    html.Span(
                        "Notification display is implemented; external "
                        "delivery such as SMS/email is not connected."
                    ),
                ],
            ),
            # Section A — Formal Notifications
            html.Section(
                className="notification-section",
                children=[
                    html.Div(
                        className="device-section__eyebrow",
                        children="Notifications",
                    ),
                    html.H2("Formal Notifications"),
                    html.P(
                        "Current notifications derived from latest-reading "
                        "freshness (BR008) and persisted device events, "
                        "newest first.",
                        className="notification-section__desc",
                    ),
                    # Summary — text-first context for the table (ENT-4 D4).
                    html.Div(
                        id="notification-summary",
                        className="notification-summary",
                    ),
                    # Error slot
                    html.Div(id="notification-error", className="listing-error"),
                    html.Div(id="notification-action-result", className="listing-error"),
                    # Notification table
                    entity_table(
                        table_id="notification-table",
                        columns=[
                            {"name": "Time", "id": "occurred_at"},
                            {"name": "Entity", "id": "entity_label"},
                            {"name": "Type", "id": "entity_type"},
                            {"name": "Notification", "id": "notification_type"},
                            {"name": "State", "id": "acknowledgement_state"},
                            {"name": "Detail", "id": "detail"},
                        ],
                        rows=[],
                        link_column_id="entity_label",
                        responsive=True,
                        extra_wrapper_class="entity-table-wrapper--notification-axis",
                        extra_style_data_conditional=[
                            _UNREGISTERED_PLAIN_TEXT_STYLE,
                        ],
                    ),
                    # Empty state — truthful across ALL categories; the list
                    # is BR008 plus persisted events, not only data-loss.
                    html.Div(
                        id="notification-empty",
                        className="status-panel status-panel--inactive",
                        style={"display": "none"},
                        children=[
                            html.P(
                                "No current notifications."
                            ),
                        ],
                    ),
                ],
            ),
            # Section B — Supported Notification Types
            html.Section(
                className="notification-section",
                children=[
                    html.Div(
                        className="device-section__eyebrow",
                        children="Reference",
                    ),
                    html.H2("Supported Notification Types"),
                    html.P(
                        "The following notification categories are confirmed by the "
                        "RTL Functional Specification. Data availability depends on "
                        "backend integration.",
                        className="notification-section__desc",
                    ),
                    html.P(
                        "Per BR009, Power Down and Sensor Error alarms both appear "
                        "in the table above under the client-facing label "
                        "“Comms Alarm”; only Battery Alarm keeps its own "
                        "label. The two conditions below remain listed separately "
                        "here because their underlying business rules (BR002/BR011 "
                        "and BR013) and data sources differ.",
                        className="notification-section__desc",
                    ),
                    # Supported types table
                    html.Div(
                        id="supported-types-container",
                        children=[
                            entity_table(
                                table_id="supported-types-table",
                                columns=[
                                    {"name": "Notification Type", "id": "label"},
                                    {"name": "Description", "id": "description"},
                                    {"name": "Data Source", "id": "data_source"},
                                ],
                                rows=[
                                    {
                                        "id": cat.key,
                                        "label": cat.label,
                                        "description": cat.description,
                                        "data_source": (
                                            "Available from current frontend data"
                                            if cat.derivable_from_frontend_data
                                            else "Requires backend/data integration"
                                        ),
                                    }
                                    for cat in all_categories()
                                ],
                                link_column_id="label",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
