"""Notification Center callbacks — wire notification data to the page.

Derives the formal >24h no-data notification (BR008) plus persisted
device_events through the shared event-semantics layer (EVT-CONSUME-1).
No external delivery is performed. Persisted reportable alarms may carry an
internal acknowledgement; acknowledgement does not clear or resolve an alarm.

ENT-4: the operator-facing list order is owned by
`notification_service.current_notifications` (newest-first); the summary line
walks the configured category order so counts can never imply priority; the
entity cell navigates in-app through the shared active_cell pattern, with
unregistered-UID rows rendered as plain text.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update, html

from components.status_panels import action_refused_notice, error_panel
from services import alarm_acknowledgement_service, monitoring_service
from services.auth_service import current_identity
from services.action_guard import may_action, require_action
from services.authorization import ACKNOWLEDGE_ALARM, ADMINISTRATOR, AuthorizationError
from services.device_scope import current_device_scope
from services.notification_service import (
    current_notifications,
    notification_summary,
    summary_category_order,
)

logger = logging.getLogger(__name__)

NOTIFICATION_LINK_COLUMN = "entity_label"
ACKNOWLEDGE_COLUMN = "acknowledge_action"


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


def notification_columns_and_rows(notifications, user, scope) -> tuple[list[dict], list[dict]]:
    """Format Notification Center rows and role-gated acknowledgement action.

    This pure presentation seam lets tests prove that General has no action
    column and a Technician only receives controls within their supplied
    trusted scope.  The callback still re-authorizes every click.
    """
    columns = [
        {"name": "Time", "id": "occurred_at"},
        {"name": "Entity", "id": "entity_label"},
        {"name": "Type", "id": "entity_type"},
        {"name": "Notification", "id": "notification_type"},
        {"name": "State", "id": "acknowledgement_state"},
        {"name": "Detail", "id": "detail"},
    ]
    can_acknowledge_any = any(
        n.event_id is not None
        and n.acknowledgement_state == "Active"
        and may_action(user, ACKNOWLEDGE_ALARM, device_id=n.entity_id, scope=scope)
        for n in notifications
    )
    if can_acknowledge_any:
        columns.append({"name": "Action", "id": ACKNOWLEDGE_COLUMN})

    rows = []
    for n in notifications:
        state = n.acknowledgement_state or "—"
        if n.acknowledged_at is not None:
            state = (
                "Acknowledged · "
                f"{n.acknowledged_at.strftime('%Y-%m-%d %H:%M UTC')}"
            )
        rows.append({
            "id": n.key,
            "occurred_at": n.occurred_at.strftime("%Y-%m-%d %H:%M UTC") if n.occurred_at else "—",
            "entity_label": n.entity_label,
            "entity_type": n.entity_type,
            "notification_type": n.notification_type,
            "acknowledgement_state": state,
            "detail": n.detail,
            "_href": n.href,
            "_event_id": n.event_id,
            "_device_id": n.entity_id if n.event_id is not None else None,
            ACKNOWLEDGE_COLUMN: (
                "Acknowledge"
                if n.event_id is not None
                and n.acknowledgement_state == "Active"
                and may_action(
                    user, ACKNOWLEDGE_ALARM, device_id=n.entity_id, scope=scope,
                )
                else ""
            ),
        })
    return columns, rows


def register(app) -> None:
    """Register notification center callbacks on the Dash app."""

    @app.callback(
        Output("notification-table", "data"),
        Output("notification-table", "columns"),
        Output("notification-error", "children"),
        Output("notification-summary", "children"),
        Output("notification-empty", "style"),
        Input("page-context", "data"),
        Input("notification-refresh", "data"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def populate_notifications(context, refresh, auth_data):
        if not context or context.get("route") != "notifications":
            return no_update, no_update, no_update, no_update, no_update

        try:
            # Resolve the caller once per render (ROLE-3 invariant): scope
            # constrains device-backed rows; only administrators see the
            # quarantined unregistered-UID surface (EVT-D5 — an unknown UID
            # belongs to no device scope, so nobody scoped can own it).
            scope = current_device_scope()
            user = current_identity()
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
            columns, table_rows = notification_columns_and_rows(
                notifications, user, scope,
            )

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

    @app.callback(
        Output("notification-action-result", "children"),
        Output("notification-refresh", "data"),
        Input("notification-table", "active_cell"),
        State("notification-table", "data"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def acknowledge_notification(active_cell, table_data, auth_data):
        """Acknowledge a persisted alarm through trusted identity and scope.

        The browser chooses only a visible table row.  The action guard and
        service both resolve current server-trusted scope; the repository
        applies it again to the write.  Acknowledgement intentionally leaves
        the alarm event and notification visible as ``Acknowledged``.
        """
        if not active_cell or active_cell.get("column_id") != ACKNOWLEDGE_COLUMN:
            return no_update, no_update
        row_id = active_cell.get("row_id")
        row = next(
            (item for item in (table_data or []) if item.get("id") == row_id),
            None,
        )
        if not row or not row.get(ACKNOWLEDGE_COLUMN):
            return no_update, no_update

        user = current_identity()
        device_id = row.get("_device_id")
        event_id = row.get("_event_id")
        try:
            require_action(user, ACKNOWLEDGE_ALARM, device_id=device_id)
            result = alarm_acknowledgement_service.acknowledge_alarm(
                event_id=event_id,
                actor_user_id=user.user_id,
                scope=current_device_scope(),
            )
        except AuthorizationError:
            return action_refused_notice(), no_update
        except alarm_acknowledgement_service.AlarmAcknowledgementError as exc:
            return error_panel(str(exc)), no_update

        message = (
            "Acknowledgement recorded. This alarm remains active until a "
            "separate clearance or resolution process exists."
            if result.changed
            else "This alarm was already acknowledged. It remains active."
        )
        return (
            html.Div(
                className="status-panel status-panel--inactive",
                children=html.P(message),
            ),
            {"event_id": result.event.event_id},
        )
