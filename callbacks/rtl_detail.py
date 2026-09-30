"""The RTL detail page's one callback (RTL-UID-DETAIL-01).

One page load, or one history-window change, resolves one
``rtl_detail_service`` snapshot and fills every output. The data is the
read-only client RTL SQL Server; there is no PostgreSQL or synthetic fallback,
and an unreachable source shows the shared error panel rather than an
empty-looking RTL.

The UID comes from ``page-context``, which only ``callbacks.routing`` writes,
and only after ``route_decision`` has allowed the route for this role. This
callback therefore never sees a UID for a session that was refused — but the
service re-checks registration anyway, because a callback that trusts its
input is one refactor away from being a second way into the source.
"""
from __future__ import annotations

import logging

from dash import Input, Output, no_update

from components import rtl_detail as ui
from components.status_panels import error_panel, forbidden_panel
from pages import rtl_detail as page
from services.rtl_scope import current_rtl_scope, may_view_real_rtls
from services.rtl_detail_service import (
    DetailStatus,
    HistoryStatus,
    get_rtl_detail,
    get_temperature_history,
)

logger = logging.getLogger(__name__)

ROUTE = "rtl_detail"
OUTPUTS = 5  # body, context, history, error, history-section style


def populate(
    context,
    window_key,
    *,
    fetch_detail=get_rtl_detail,
    fetch_history=get_temperature_history,
    scope_for=current_rtl_scope,
):
    """Body of the callback, testable without a Dash runtime.

    The caller's scope is resolved here as well as by the router (a callback
    is independently invokable): nothing is fetched for a UID outside it.
    """
    if not context or context.get("route") != ROUTE:
        return (no_update,) * OUTPUTS

    device_uid = context.get("rtl_uid")
    try:
        scope = scope_for()
        if not may_view_real_rtls(scope) or (
            isinstance(device_uid, int) and not scope.allows(device_uid)
        ):
            return forbidden_panel(), None, None, None, page.HIDDEN_STYLE
        result = fetch_detail(device_uid, scope=scope)
    except Exception:
        logger.exception("Failed to load RTL detail")
        return None, None, None, error_panel(), page.HIDDEN_STYLE

    if result.status is DetailStatus.FORBIDDEN:
        return forbidden_panel(), None, None, None, page.HIDDEN_STYLE

    if result.status is DetailStatus.NOT_REGISTERED:
        # No history read at all: an unregistered UID must not reach the
        # temperature source through this page's second output either. The
        # window control is hidden too — offering "24 hours / 7 days / 30
        # days" for an RTL that does not exist implies there is something
        # behind it to select.
        return (
            ui.not_registered_panel(result.device_uid),
            None, None, None, page.HIDDEN_STYLE,
        )

    if result.status is not DetailStatus.DATA or result.rtl is None:
        return None, None, None, error_panel(ui.SOURCE_UNAVAILABLE), page.HIDDEN_STYLE

    try:
        history = fetch_history(device_uid, window_key, scope=scope)
    except Exception:
        logger.exception("Failed to load RTL temperature history")
        history = None

    return (
        ui.summary(result.rtl),
        ui.network_context(result.rtl),
        ui.history_panel(history) if history is not None else error_panel(),
        None,
        page.VISIBLE_STYLE,
    )


def register(app) -> None:
    @app.callback(
        Output(page.BODY_ID, "children"),
        Output(page.CONTEXT_ID, "children"),
        Output(page.HISTORY_ID, "children"),
        Output(page.ERROR_ID, "children"),
        Output(page.HISTORY_SECTION_ID, "style"),
        Input("page-context", "data"),
        Input(page.WINDOW_ID, "value"),
    )
    def populate_rtl_detail(context, window_key):
        return populate(context, window_key)
