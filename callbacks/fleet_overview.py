"""The Fleet Overview's one callback (FO-NEW-1, SWITCH-OVER-1).

One page load = one scope resolution (ADR-004) = one
`fleet_overview_service` snapshot = every output. A failed read shows the
shared error panel instead of an empty list, so an unreachable database never
reads as "no plants".

A filter chip or sort change re-runs the same path (POLISH-1): one fresh
snapshot, narrowed and ordered by `filter_and_sort`, with the chip counts
taken from that same snapshot.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from dash import ALL, Input, Output, ctx, no_update

from components import fleet_overview as ui
from components.status_panels import error_panel
from pages import plants_overview as page
from services.device_scope import current_device_scope
from services.fleet_overview_service import FILTER_ALL, SORT_NAME, filter_and_sort, get_fleet_overview

logger = logging.getLogger(__name__)

ROUTE = "overview"
OUTPUTS = 7  # stat cards, refreshed, limits, plants, error, filter options, condition bar


def populate(context, filter_key=FILTER_ALL, sort_key=SORT_NAME, *,
             fetch=get_fleet_overview, scope_for=current_device_scope):
    """Body of the callback, testable without a Dash runtime."""
    if not context or context.get("route") != ROUTE:
        return (no_update,) * OUTPUTS
    try:
        now = datetime.now(timezone.utc)
        view = fetch(scope_for(), now=now)
    except Exception:
        logger.exception("Failed to load the Fleet Overview")
        return None, None, None, [], error_panel(), [], None
    return (
        ui.stat_cards(view),
        f"Updated {now.strftime('%d %b %Y %H:%M UTC')}",
        ui.limits_line(view.limits),
        ui.plant_list(view, filter_and_sort(view, filter_key or FILTER_ALL, sort_key or SORT_NAME)),
        None,
        ui.filter_options(view),
        ui.condition_bar(view),
    )


def jump_outputs(trigger, clicks) -> tuple:
    """(filter value, sort value) for a click on a card or bar segment.
    Pattern inputs also fire when the cards re-render with n_clicks 0; only
    a real click acts."""
    if not clicks or not isinstance(trigger, dict):
        return no_update, no_update
    return (trigger.get("filter") or no_update, trigger.get("sort") or no_update)


def register(app) -> None:
    @app.callback(
        Output(page.STATS_ID, "children"),
        Output(page.REFRESHED_ID, "children"),
        Output(page.LIMITS_ID, "children"),
        Output(page.PLANTS_ID, "children"),
        Output(page.ERROR_ID, "children"),
        Output(page.FILTER_ID, "options"),
        Output(page.CONDITION_ID, "children"),
        Input("page-context", "data"),
        Input(page.FILTER_ID, "value"),
        Input(page.SORT_ID, "value"),
    )
    def populate_fleet_overview(context, filter_key, sort_key):
        return populate(context, filter_key, sort_key)

    @app.callback(
        Output(page.FILTER_ID, "value"),
        Output(page.SORT_ID, "value"),
        Input({"type": ui.JUMP, "part": ALL, "filter": ALL, "sort": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def jump_from_card(_clicks):
        value = ctx.triggered[0]["value"] if ctx.triggered else None
        return jump_outputs(ctx.triggered_id, value)
