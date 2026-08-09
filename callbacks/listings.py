"""Listing callbacks — populate drill-down tables and handle row navigation.

Row builders and navigation targets are module-level functions so they can be
tested without a Dash runtime; `register()` only wires them up.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update

from components.status_panels import error_panel
from routes import device_href
from services import hierarchy_service

logger = logging.getLogger(__name__)

# The column whose cells are styled as links and whose clicks navigate.
PLANT_LINK_COLUMN = "plant"
TRANSFORMER_LINK_COLUMN = "transformer"
DEVICE_LINK_COLUMN = "device"

PLANT_COLUMNS = [
    {"name": "Plant", "id": "plant"},
    {"name": "Country", "id": "country"},
    {"name": "Fuel", "id": "fuel"},
    # Numeric so native sorting orders 900 < 1,000 < 12,000 instead of sorting
    # the formatted strings lexically. The unit lives in the header.
    {"name": "Capacity (MW)", "id": "capacity_mw", "type": "numeric"},
    {"name": "Transformers", "id": "transformers", "type": "numeric"},
    {"name": "Devices", "id": "devices", "type": "numeric"},
]

TRANSFORMER_COLUMNS = [
    {"name": "Transformer", "id": "transformer"},
    {"name": "Devices", "id": "devices", "type": "numeric"},
    {"name": "Status", "id": "status"},
]

DEVICE_COLUMNS = [
    {"name": "Device", "id": "device"},
    {"name": "Status", "id": "status"},
]


# --------------------------------------------------------------------------
# Row builders
#
# Every row carries an `id`. dash_table surfaces it as `active_cell["row_id"]`,
# which is what makes click navigation independent of sorting/filtering/paging.
# `id` is not listed in the column specs, so it is never rendered.
# --------------------------------------------------------------------------

def build_plant_rows(plants, counts: dict) -> list[dict]:
    rows = []
    for p in plants:
        t_count, d_count = counts.get(p.plant_id, (0, 0))
        rows.append({
            "id": p.plant_id,
            "plant": p.name,
            "country": p.country,
            "fuel": p.primary_fuel or "",
            "capacity_mw": p.capacity_mw,
            "transformers": t_count,
            "devices": d_count,
        })
    return rows


def build_transformer_rows(transformers, device_counts: dict) -> list[dict]:
    return [
        {
            "id": t.transformer_id,
            "transformer": t.transformer_code,
            "devices": device_counts.get(t.transformer_id, 0),
            "status": t.status,
        }
        for t in transformers
    ]


def build_device_rows(devices) -> list[dict]:
    return [
        {"id": d.device_id, "device": d.device_code, "status": d.status}
        for d in devices
    ]


# --------------------------------------------------------------------------
# Navigation targets
# --------------------------------------------------------------------------

def _clicked_row_id(active_cell, link_column: str) -> str | None:
    """The identity of the clicked row, or None if this click should be ignored.

    Deliberately reads `row_id` rather than indexing `data` by
    `active_cell["row"]`: that index refers to the sorted/filtered/paged
    viewport, so it points at the wrong entity as soon as the operator sorts a
    column.
    """
    if not active_cell or active_cell.get("column_id") != link_column:
        return None
    return active_cell.get("row_id") or None


def plant_row_target(active_cell):
    plant_id = _clicked_row_id(active_cell, PLANT_LINK_COLUMN)
    if not plant_id:
        return no_update
    return f"/plants/{plant_id}"


def transformer_row_target(active_cell, context):
    transformer_id = _clicked_row_id(active_cell, TRANSFORMER_LINK_COLUMN)
    if not transformer_id:
        return no_update
    plant_id = (context or {}).get("plant_id")
    if not plant_id:
        return no_update
    return f"/plants/{plant_id}/{transformer_id}"


def device_row_target(active_cell):
    device_id = _clicked_row_id(active_cell, DEVICE_LINK_COLUMN)
    if not device_id:
        return no_update
    return device_href(device_id)


def listing_outputs(build_rows, columns: list[dict], context_msg: str) -> tuple:
    """(rows, columns, error_children) for one listing table.

    The three listing callbacks previously called services with no boundary. The
    overview route does no database access itself, so an outage after login first
    surfaced here and raised through Dash, leaving a page that never filled in.

    An empty table alone is not enough: "no rows exist" and "we could not reach
    the database" must not look identical, hence the separate error slot. The
    cause is logged in full; the panel stays generic per CLAUDE.md.
    """
    try:
        return build_rows(), columns, None
    except Exception:
        logger.exception("Listing failed while %s", context_msg)
        return [], columns, error_panel()


def register(app) -> None:
    """Register listing callbacks on the Dash app."""

    @app.callback(
        Output("plants-table", "data"),
        Output("plants-table", "columns"),
        Output("plants-error", "children"),
        Input("page-context", "data"),
        prevent_initial_call=True,
    )
    def populate_overview(context):
        if not context or context.get("route") != "overview":
            return no_update, no_update, no_update

        def build():
            plants = hierarchy_service.list_plants()
            counts = hierarchy_service.get_plant_hierarchy_counts()
            return build_plant_rows(plants, counts)

        return listing_outputs(build, PLANT_COLUMNS, "loading the plants overview")

    @app.callback(
        Output("transformers-table", "data"),
        Output("transformers-table", "columns"),
        Output("transformers-error", "children"),
        Input("page-context", "data"),
        prevent_initial_call=True,
    )
    def populate_plant_detail(context):
        if not context or context.get("route") != "plant":
            return no_update, no_update, no_update
        plant_id = context.get("plant_id")

        def build():
            transformers = hierarchy_service.list_transformers(plant_id)
            device_counts = {
                t.transformer_id: len(hierarchy_service.list_devices(t.transformer_id))
                for t in transformers
            }
            return build_transformer_rows(transformers, device_counts)

        return listing_outputs(
            build, TRANSFORMER_COLUMNS, f"loading transformers for plant_id={plant_id!r}"
        )

    @app.callback(
        Output("devices-table", "data"),
        Output("devices-table", "columns"),
        Output("devices-error", "children"),
        Input("page-context", "data"),
        prevent_initial_call=True,
    )
    def populate_transformer_detail(context):
        if not context or context.get("route") != "transformer":
            return no_update, no_update, no_update
        transformer_id = context.get("transformer_id")

        return listing_outputs(
            lambda: build_device_rows(hierarchy_service.list_devices(transformer_id)),
            DEVICE_COLUMNS,
            f"loading devices for transformer_id={transformer_id!r}",
        )

    # Row-click navigation. dash_table has no non-markdown way to render a cell
    # as a link, and markdown-presentation links are hardcoded by dash_table to
    # target="_blank" (breaking in-app navigation) — so these tables render
    # plain text and a click on the identity column navigates via
    # `url.pathname`.

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("plants-table", "active_cell"),
        prevent_initial_call=True,
    )
    def navigate_from_plants_table(active_cell):
        return plant_row_target(active_cell)

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("transformers-table", "active_cell"),
        State("page-context", "data"),
        prevent_initial_call=True,
    )
    def navigate_from_transformers_table(active_cell, context):
        return transformer_row_target(active_cell, context)

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("devices-table", "active_cell"),
        prevent_initial_call=True,
    )
    def navigate_from_devices_table(active_cell):
        return device_row_target(active_cell)
