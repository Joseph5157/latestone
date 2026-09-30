"""Historical Events callbacks (HISTORICAL-EVENTS-01).

Both callbacks re-check ``may_view_real_fleet`` before any event source is
read, so a restricted session that reaches the layout still gets nothing.
"""
from __future__ import annotations

import logging
from datetime import date

from dash import Input, Output, State, ctx, no_update

from components import historical_events as ui
from pages import historical_events as page
from services import rtl_events_service as svc
from services.device_scope import current_device_scope

logger = logging.getLogger(__name__)

ROUTE = "historical_events"


def _day(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def initial_window(context, *, latest=svc.get_latest_event_time, scope_for=current_device_scope):
    """(start, end) ISO dates for the default window, or no_update."""
    if not context or context.get("route") != ROUTE:
        return no_update, no_update
    try:
        if not svc.may_view_real_fleet(scope_for()):
            return None, None
        window = svc.default_window(latest())
    except Exception:
        logger.exception("Failed to set the Historical Events window")
        return None, None
    if window is None:
        return None, None
    return window[0].isoformat(), window[1].isoformat()


def render(context, start, end, event_type, uid_text, trigger, current_page, *,
           fetch=svc.get_events_page, scope_for=current_device_scope):
    """(body, page). ``trigger`` is the id of the input that fired, if any."""
    if not context or context.get("route") != ROUTE:
        return no_update, no_update
    try:
        if not svc.may_view_real_fleet(scope_for()):
            return None, 0
    except Exception:
        logger.exception("Historical Events scope check failed")
        return None, 0
    start_day, end_day = _day(start), _day(end)
    if start_day is None or end_day is None:
        return ui.message("Choose a date range to list events."), 0
    wanted = current_page or 0
    if trigger == page.NEXT_ID:
        wanted += 1
    elif trigger == page.PREV_ID:
        wanted -= 1
    else:
        wanted = 0  # any filter change starts from the newest events
    kind = None if event_type in (None, page.ALL_TYPES) else event_type
    try:
        result = fetch(start_day, end_day, kind, uid_text, wanted)
    except Exception:
        logger.exception("Failed to load Historical Events")
        return ui.message("Historical events are unavailable right now."), 0
    if result.status is svc.EventsStatus.INVALID:
        return ui.message(ui.INVALID), 0
    if result.status is not svc.EventsStatus.DATA:
        return ui.message("Historical events are unavailable right now."), 0
    return ui.body(result), result.page


def register(app) -> None:
    @app.callback(
        Output(page.START_ID, "start_date"),
        Output(page.START_ID, "end_date"),
        Input("page-context", "data"),
    )
    def set_window(context):
        return initial_window(context)

    @app.callback(
        Output(page.BODY_ID, "children"),
        Output(page.PAGE_STORE_ID, "data"),
        Input(page.START_ID, "start_date"),
        Input(page.START_ID, "end_date"),
        Input(page.TYPE_ID, "value"),
        Input(page.UID_ID, "value"),
        Input(page.PREV_ID, "n_clicks"),
        Input(page.NEXT_ID, "n_clicks"),
        State(page.PAGE_STORE_ID, "data"),
        State("page-context", "data"),
    )
    def render_events(start, end, event_type, uid_text, _prev, _next, current_page, context):
        return render(context, start, end, event_type, uid_text, ctx.triggered_id, current_page)
