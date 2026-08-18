"""Notification Center page — layout only, no queries.

Frontend shell for notification center. Notification categories are confirmed
by the RTL Functional Specification (§3, §11). Notification generation,
delivery, and persistence remain prototype-only.
"""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.entity_table import entity_table
from config.notifications import all_categories


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
            # Prototype notice
            html.Div(
                className="status-panel status-panel--inactive",
                children=[
                    html.Strong("Prototype. "),
                    html.Span(
                        "Notification categories are confirmed by the Functional "
                        "Specification. Actual notification generation and delivery "
                        "require backend integration."
                    ),
                ],
            ),
            # Section A — Formal Notifications
            html.Section(
                className="notification-section",
                children=[
                    html.H2("Formal Notifications"),
                    html.P(
                        "Business notification rules confirmed by the RTL Functional "
                        "Specification (BR008). These are derived from current frontend "
                        "data where available.",
                        className="notification-section__desc",
                    ),
                    # Summary
                    html.Div(
                        id="notification-summary",
                        className="notification-summary",
                    ),
                    # Error slot
                    html.Div(id="notification-error", className="listing-error"),
                    # Notification table
                    entity_table(
                        table_id="notification-table",
                        columns=[
                            {"name": "Last Data", "id": "occurred_at"},
                            {"name": "Entity", "id": "entity_label", "presentation": "markdown"},
                            {"name": "Type", "id": "entity_type"},
                            {"name": "Notification", "id": "notification_type"},
                            {"name": "Detail", "id": "detail"},
                        ],
                        rows=[],
                        link_column_id="entity_label",
                    ),
                    # Empty state
                    html.Div(
                        id="notification-empty",
                        className="status-panel status-panel--inactive",
                        style={"display": "none"},
                        children=[
                            html.P(
                                "No current >24-hour data-loss notifications."
                            ),
                        ],
                    ),
                ],
            ),
            # Section B — Supported Notification Types
            html.Section(
                className="notification-section",
                children=[
                    html.H2("Supported Notification Types"),
                    html.P(
                        "The following notification categories are confirmed by the "
                        "RTL Functional Specification. Data availability depends on "
                        "backend integration.",
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
