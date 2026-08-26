"""Notification Center callbacks — wire notification data to the page.

Derives the formal >24h no-data notification (BR008) plus persisted
device_events through the shared event-semantics layer (EVT-CONSUME-1).
Display-only: no files are produced, no SMS/email is sent, no notification
history is persisted.

ENT-4: the operator-facing list order is owned by
`notification_service.current_notifications` (newest-first); the summary line
walks the configured category order so counts can never imply priority; the
entity cell navigates in-app through the shared active_cell pattern, with
unregistered-UID rows rendered as plain text.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update, html

from components.status_panels import error_panel
from services import monitoring_service
from services.auth_service import from_session
from services.authorization import ADMINISTRATOR
from services.device_scope import scope_from_session
from services.notification_service import (
    current_notifications,
    notification_summary,
    summary_category_order,
)

logger = logging.getLogger(__name__)

NOTIFICATION_LINK_COLUMN = "entity_label"


def format_summary_line(total: int, by_type: dict) -> str:
    """The text-first summary line (ENT-4 gate decision D4).

    Categories appear in the configured spec order — never by count, which
    would imply priority — and zero-count categories are omitted. Reads as
    context for the table, not another dashboard layer.
    """
    parts = [f"{total} current notification{'s' if total != 1 else ''}"]
    for label in summary_category_order():
        count = by_type.get(label, 0)
        if count:
            parts.append(f"{label} {count}")
    return " · ".join(parts)


def notification_row_target(active_cell, table_data) -> object:
    """The in-app route for a clicked entity cell, or no_update.

    Same contract as the hierarchy tables: only the entity column triggers,
    and `row_id` (not the viewport row index) identifies the row, so sorting
    or filtering cannot send the operator to the wrong device. Unregistered
    UID rows carry an empty `_href` and resolve to no_update — they must not
    look or behave clickable.
    """
    if not active_cell or active_cell.get("column_id") != NOTIFICATION_LINK_COLUMN:
        return no_update
    row_id = active_cell.get("row_id")
    if not row_id:
        return no_update
    for row in table_data or []:
        if row.get("id") == row_id:
            href = row.get("_href")
            return href or no_update
    return no_update


def register(app) -> None:
    """Register notification center callbacks on the Dash app."""

    @app.callback(
        Output("notification-table", "data"),
        Output("notification-table", "columns"),
        Output("notification-error", "children"),
        Output("notification-summary", "children"),
        Output("notification-empty", "style"),
        Input("page-context", "data"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def populate_notifications(context, auth_data):
        if not context or context.get("route") != "notifications":
            return no_update, no_update, no_update, no_update, no_update

        try:
            # Resolve the caller once per render (ROLE-3 invariant): scope
            # constrains device-backed rows; only administrators see the
            # quarantined unregistered-UID surface (EVT-D5 — an unknown UID
            # belongs to no device scope, so nobody scoped can own it).
            scope = scope_from_session(auth_data)
            user = from_session(auth_data)
            is_admin = user is not None and user.role == ADMINISTRATOR

            rows = monitoring_service.latest_reading_rows(scope=scope)

            # Formal >24h no-data + persisted device_events (via the shared
            # event-semantics layer, EVT-D1/D3). Newest-first is owned by the
            # service composition (ENT-4).
            notifications = current_notifications(
                reading_rows=rows,
                scope=scope,
                include_unregistered=is_admin,
            )

            # Summary — text-first, configured category order (D4).
            summary = notification_summary(notifications)
            summary_text = format_summary_line(
                summary["total"], summary["by_type"]
            )

            # Empty state
            empty_style = {"display": "block"} if not notifications else {"display": "none"}

            # Table columns. The entity cell is plain text styled as a link by
            # link_column_id; navigation runs through active_cell below (the
            # markdown route hardcodes target="_blank", which breaks in-app
            # navigation).
            columns = [
                {"name": "Time", "id": "occurred_at"},
                {"name": "Entity", "id": "entity_label"},
                {"name": "Type", "id": "entity_type"},
                {"name": "Notification", "id": "notification_type"},
                {"name": "Detail", "id": "detail"},
            ]

            # Format rows for display. `_href` rides along as a hidden key for
            # the navigation callback; unregistered UIDs carry an empty one.
            table_rows = []
            for n in notifications:
                table_rows.append({
                    "id": n.key,
                    "occurred_at": n.occurred_at.strftime("%Y-%m-%d %H:%M UTC") if n.occurred_at else "—",
                    "entity_label": n.entity_label,
                    "entity_type": n.entity_type,
                    "notification_type": n.notification_type,
                    "detail": n.detail,
                    "_href": n.href,
                })

            return table_rows, columns, None, summary_text, empty_style

        except Exception:
            logger.exception("Failed to load notifications")
            return [], [], error_panel(), None, {"display": "none"}

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("notification-table", "active_cell"),
        State("notification-table", "data"),
        prevent_initial_call=True,
    )
    def navigate_from_notification_table(active_cell, table_data):
        return notification_row_target(active_cell, table_data)
