"""The Network page's two callbacks (LATEST-NETWORK-CONTEXT-01).

``load`` runs once per page load: one scope resolution (ADR-004), one
``rtl_network_service`` snapshot of the read-only client RTL SQL Server, stored
in the page. There is no PostgreSQL or synthetic fallback; an unreachable
source shows the shared error panel, never an empty network. Roles without an
approved raw-RTL visibility rule get the restricted panel and the source is not
read for them.

``render`` runs on every filter change over that stored snapshot - no further
source reads - and returns the cascade-normalised selection, so a changed
parent level can never leave a stale child selected.
"""
from __future__ import annotations

import logging

from dash import Input, Output, no_update

from components import rtl_network as ui
from components.status_panels import error_panel
from pages import rtl_network as page
from services import rtl_network_service as svc
from services.device_scope import current_device_scope

logger = logging.getLogger(__name__)

ROUTE = "rtl_network"


def load(context, *, fetch=svc.get_current_network, scope_for=current_device_scope):
    """Body of the load callback: (store payload, error children)."""
    if not context or context.get("route") != ROUTE:
        return no_update, no_update
    try:
        if not svc.may_view_real_fleet(scope_for()):
            return None, ui.restricted_panel()
        network = fetch()
    except Exception:
        logger.exception("Failed to load the Network view")
        return None, error_panel()
    if network.status is not svc.NetworkStatus.DATA:
        return None, error_panel("The client RTL data source is unavailable. No RTL data is shown.")
    return svc.to_payload(network.rows), None


def render(payload, scope, *levels):
    """Body of the render callback over the stored snapshot."""
    rows = svc.from_payload(payload)
    if not rows:
        empty_options = [[] for _ in svc.LEVELS]
        empty_values = [None for _ in svc.LEVELS]
        return (None, None, None, [], *empty_options, *empty_values)
    selection = svc.normalise_filter(
        rows, svc.NetworkFilter(scope or svc.SCOPE_ALL, **dict(zip(svc.LEVELS, levels)))
    )
    in_view = svc.filter_rows(rows, selection)
    options = svc.cascade_options(rows, selection)
    return (
        ui.summary_cards(svc.summarise(in_view), len(rows)),
        ui.breakdown(in_view, svc.next_level(selection)),
        ui.network_table(in_view),
        ui.scope_options(rows),
        *[ui.level_dropdown_options(options[level]) for level in svc.LEVELS],
        *[selection.value(level) for level in svc.LEVELS],
    )


def register(app) -> None:
    @app.callback(
        Output(page.STORE_ID, "data"),
        Output(page.ERROR_ID, "children"),
        Input("page-context", "data"),
    )
    def load_rtl_network(context):
        return load(context)

    @app.callback(
        Output(page.STATS_ID, "children"),
        Output(page.BREAKDOWN_ID, "children"),
        Output(page.LIST_ID, "children"),
        Output(page.SCOPE_ID, "options"),
        *[Output(page.filter_id(level), "options") for level in svc.LEVELS],
        *[Output(page.filter_id(level), "value") for level in svc.LEVELS],
        Input(page.STORE_ID, "data"),
        Input(page.SCOPE_ID, "value"),
        *[Input(page.filter_id(level), "value") for level in svc.LEVELS],
    )
    def render_rtl_network(payload, scope, *levels):
        return render(payload, scope, *levels)
