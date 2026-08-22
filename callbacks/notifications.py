"""Notification Center callbacks — wire notification data to the page.

All operations are frontend-only. Notification categories are confirmed by the
RTL Functional Specification (§3, §11). No files are produced or delivered.
No SMS/email/backend claims are made.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update, html

from services import monitoring_service
from services.device_scope import scope_from_session
from services.notification_service import build_current_notifications, notification_summary

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
            # Get fleet-wide latest reading data, constrained to what this
            # caller may see — resolved once per render (ROLE-3 invariant).
            scope = scope_from_session(auth_data)
            rows = monitoring_service.latest_reading_rows(scope=scope)

            # Build formal notifications (>24h no-data)
            notifications = build_current_notifications(rows)

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
