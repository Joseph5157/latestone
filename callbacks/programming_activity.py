"""Programming activity visibility on the shared RTL device page.

The callback is deliberately read-only.  It resolves both identity and scope
on the server, then uses the existing Program RTL action policy to decide who
may see the operational history: Administrator on any RTL, Technician on a
current assignment only, and no General User visibility.
"""
from __future__ import annotations

from dash import Input, Output

from components.programming_activity import (
    PROGRAMMING_ACTIVITY_ID,
    programming_activity_error,
    programming_activity_panel,
)
from components.device_manage_drawer import PROGRAM_RTL_LAST_REQUEST_ID
from services import rtl_programming_activity_service as activity_service
from services.action_guard import may_action
from services.auth_service import current_identity
from services.authorization import PROGRAM_RTL
from services.device_scope import current_device_scope


def programming_activity_children(user, device_id: str, *, scope):
    """Return an authorized RTL's activity panel, or no panel at all.

    ``may_action`` is intentionally reused for visibility instead of making a
    role comparison or a second assignment predicate.  The same trusted scope
    is passed to the reader, so a forged route/context cannot broaden either
    the permission check or the SQL query.
    """
    if not device_id or not may_action(
        user, PROGRAM_RTL, device_id=device_id, scope=scope
    ):
        return None
    try:
        records = activity_service.recent_activity(device_id, scope=scope)
    except activity_service.ProgrammingActivityError:
        return programming_activity_error()
    return programming_activity_panel(records)


def register(app) -> None:
    """Register the device-route activity renderer."""
    @app.callback(
        Output(PROGRAMMING_ACTIVITY_ID, "children"),
        Input("page-context", "data"),
        Input("auth-store", "data"),
        Input(PROGRAM_RTL_LAST_REQUEST_ID, "data"),
    )
    def render_programming_activity(page_context, auth_data, _last_request_id):
        """Use server-trusted identity; ``auth_data`` only triggers rerender."""
        context = page_context or {}
        if context.get("route") != "device":
            return None
        user = current_identity()
        scope = current_device_scope()
        return programming_activity_children(
            user, context.get("device_id", ""), scope=scope
        )


__all__ = ["programming_activity_children", "register"]
