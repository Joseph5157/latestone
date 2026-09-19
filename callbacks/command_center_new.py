"""The redesigned Command Center's one populate callback (CC-NEW-1).

One interval tick = one `attention_service` snapshot = one render of every
panel (ADR-005). Failure handling matches the old page: a failed first load
shows the error state; a failed refresh keeps the last good panels on screen
and says the data is stale, never blanking correct information.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from dash import Input, Output, State, no_update

from components import attention as ui
from components.command_center import refresh
from components.command_center.primitives import scope_indicator_text
from components.status_panels import error_panel
from pages import command_center_new as page
from services.attention_service import get_attention_snapshot
from services.device_scope import current_device_scope

logger = logging.getLogger(__name__)

ROUTE = "command_center_new"
PANEL_OUTPUTS = 6  # scope, status, problems, hottest, activity, trend


def _last_success(state) -> datetime | None:
    stamp = (state or {}).get("last_success_at")
    try:
        return datetime.fromisoformat(stamp) if stamp else None
    except (TypeError, ValueError):
        return None


def render_panels(snapshot) -> tuple:
    now = snapshot.generated_at
    return (
        scope_indicator_text(snapshot.total_rtls),
        ui.status_bar(snapshot),
        ui.problem_list(snapshot.problems, now),
        ui.hottest_card(snapshot.hottest),
        ui.activity_card(snapshot.activity, now),
        ui.alarm_trend_card(snapshot.daily_alarms),
    )


def populate(context, refresh_state, *, fetch=get_attention_snapshot, scope_for=current_device_scope):
    """Pure-ish body of the callback, testable without a Dash runtime."""
    if not context or context.get("route") != ROUTE:
        return (no_update,) * (PANEL_OUTPUTS + 3)
    try:
        fetched_at = datetime.now(timezone.utc)
        snapshot = fetch(scope_for(), now=fetched_at)
        return render_panels(snapshot) + (
            None,
            refresh.refresh_status(fetched_at, failed=False),
            {"last_success_at": fetched_at.isoformat(), "failed": False},
        )
    except Exception:
        logger.exception("Failed to load the Command Center snapshot")
        last = _last_success(refresh_state)
        if last is None:
            return (no_update,) + ([],) * (PANEL_OUTPUTS - 1) + (
                error_panel(),
                refresh.refresh_status(None, failed=False),
                {"last_success_at": None, "failed": True},
            )
        return (no_update,) * PANEL_OUTPUTS + (
            no_update,
            refresh.refresh_status(last, failed=True),
            {"last_success_at": refresh_state["last_success_at"], "failed": True},
        )


def register(app) -> None:
    @app.callback(
        Output(page.SCOPE_ID, "children"),
        Output(page.STATUS_SLOT_ID, "children"),
        Output(page.PROBLEMS_ID, "children"),
        Output(page.HOTTEST_ID, "children"),
        Output(page.ACTIVITY_ID, "children"),
        Output(page.TREND_ID, "children"),
        Output(page.ERROR_ID, "children"),
        Output(page.REFRESH_STATUS_ID, "children"),
        Output(page.STORE_ID, "data"),
        Input("page-context", "data"),
        Input(page.INTERVAL_ID, "n_intervals"),
        Input(page.REFRESH_NOW_ID, "n_clicks"),
        State(page.STORE_ID, "data"),
    )
    def populate_attention(context, _ticks, _clicks, refresh_state):
        return populate(context, refresh_state)
