"""Trusted, read-only callback for the Administrator audit-log viewer."""
from __future__ import annotations

from dash import Input, Output, no_update

from components.status_panels import error_panel
from pages.audit_log import AUDIT_LOG_ERROR_ID, AUDIT_LOG_SUMMARY_ID, AUDIT_LOG_TABLE_ID
from services import audit_log_service
from services.action_guard import require_capability
from services.auth_service import current_identity
from services.authorization import AuthorizationError, VIEW_AUDIT_LOG


AUDIT_LOG_COLUMNS = [
    {"name": "Timestamp", "id": "occurred_at"},
    {"name": "Actor", "id": "actor"},
    {"name": "Action", "id": "operation"},
    {"name": "Entity type", "id": "entity_type"},
    {"name": "Entity ID", "id": "entity_id"},
]


def audit_log_rows(records) -> list[dict]:
    """Format the safe repository read model without exposing audit payloads."""
    return [
        {
            "id": record.audit_id,
            "occurred_at": record.occurred_at.strftime("%Y-%m-%d %H:%M UTC"),
            "actor": record.actor_name,
            "operation": record.operation,
            "entity_type": record.entity_type,
            "entity_id": record.entity_id,
        }
        for record in records
    ]


def audit_log_outputs(user):
    """Build the viewer data after enforcing its device-less capability."""
    require_capability(user, VIEW_AUDIT_LOG)
    try:
        records = audit_log_service.recent_audit_log()
    except audit_log_service.AuditLogViewerError:
        return [], AUDIT_LOG_COLUMNS, error_panel(), ""
    rows = audit_log_rows(records)
    noun = "record" if len(rows) == 1 else "records"
    return rows, AUDIT_LOG_COLUMNS, None, f"Showing {len(rows)} newest audit {noun}"


def register(app) -> None:
    """Register the server-trusted read-only viewer callback."""

    @app.callback(
        Output(AUDIT_LOG_TABLE_ID, "data"),
        Output(AUDIT_LOG_TABLE_ID, "columns"),
        Output(AUDIT_LOG_ERROR_ID, "children"),
        Output(AUDIT_LOG_SUMMARY_ID, "children"),
        Input("page-context", "data"),
        Input("auth-store", "data"),
        prevent_initial_call=True,
    )
    def render_audit_log(page_context, _auth_data):
        if (page_context or {}).get("route") != "audit_log":
            return (no_update,) * 4
        try:
            return audit_log_outputs(current_identity())
        except AuthorizationError:
            return (no_update,) * 4
