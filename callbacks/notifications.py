"""Notification Center callbacks — wire notification data to the page.

Derives the formal >24h no-data notification (BR008) plus persisted
device_events through the shared event-semantics layer (EVT-CONSUME-1).
Display-only: no files are produced, no SMS/email is sent, no notification
history is persisted.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update, html

from services import monitoring_service
from services.auth_service import from_session
from services.authorization import ADMINISTRATOR
from services.device_scope import scope_from_session
from services.notification_service import current_notifications, notification_summary

logger = logging.getLogger(__name__)


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
            # event-semantics layer, EVT-D1/D3).
            notifications = current_notifications(
                reading_rows=rows,
                scope=scope,
                include_unregistered=is_admin,
            )

            # Summary
            summary = notification_summary(notifications)
            summary_text = html.Div(
                className="notification-summary__content",
                children=[
                    html.Strong(f"{summary['total']}"),
                    " current notification(s) established from available frontend data.",
                ],
            )

            # Empty state
            empty_style = {"display": "block"} if not notifications else {"display": "none"}

            # Table columns
            columns = [
                {"name": "Last Data", "id": "occurred_at"},
                {"name": "Entity", "id": "entity_label", "presentation": "markdown"},
                {"name": "Type", "id": "entity_type"},
                {"name": "Notification", "id": "notification_type"},
                {"name": "Detail", "id": "detail"},
            ]

            # Format rows for display
            table_rows = []
            for n in notifications:
                table_rows.append({
                    "id": n.key,
                    "occurred_at": n.occurred_at.strftime("%Y-%m-%d %H:%M UTC") if n.occurred_at else "—",
                    "entity_label": f"[{n.entity_label}]({n.href})",
                    "entity_type": n.entity_type,
                    "notification_type": n.notification_type,
                    "detail": n.detail,
                })

            return table_rows, columns, None, summary_text, empty_style

        except Exception:
            logger.exception("Failed to load notifications")
            return [], [], "Error loading notifications.", None, {"display": "none"}
