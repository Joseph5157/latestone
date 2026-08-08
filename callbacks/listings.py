"""Listing callbacks — populate drill-down tables and the cascading selector."""
from __future__ import annotations

from dash import Input, Output, State, callback, no_update

from callbacks.routing import device_href
from services import hierarchy_service, monitoring_service


PLANT_COLUMNS = [
    {"name": "Plant", "id": "plant"},
    {"name": "Country", "id": "country"},
    {"name": "Fuel", "id": "fuel"},
    {"name": "Capacity", "id": "capacity"},
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


def register(app) -> None:
    """Register listing callbacks on the Dash app."""

    @app.callback(
        Output("plants-table", "data"),
        Output("plants-table", "columns"),
        Input("page-context", "data"),
        prevent_initial_call=True,
    )
    def populate_overview(context):
        if not context or context.get("route") != "overview":
            return no_update, no_update

        plants = hierarchy_service.list_plants()
        counts = hierarchy_service.get_plant_hierarchy_counts()

        rows = []
        for p in plants:
            t_count, d_count = counts.get(p.plant_id, (0, 0))
            rows.append({
                "plant": p.name,
                "plant_id": p.plant_id,
                "country": p.country,
                "fuel": p.primary_fuel or "",
                "capacity": f"{p.capacity_mw:,.0f} MW" if p.capacity_mw else "",
                "transformers": t_count,
                "devices": d_count,
            })

        return rows, PLANT_COLUMNS

    @app.callback(
        Output("transformers-table", "data"),
        Output("transformers-table", "columns"),
        Input("page-context", "data"),
        prevent_initial_call=True,
    )
    def populate_plant_detail(context):
        if not context or context.get("route") != "plant":
            return no_update, no_update

        plant_id = context.get("plant_id")
        plant_name = context.get("plant_name", "")
        transformers = hierarchy_service.list_transformers(plant_id)
        counts = hierarchy_service.get_plant_hierarchy_counts()
        _, total_devices = counts.get(plant_id, (0, 0))

        # Count devices per transformer
        device_counts = {}
        for t in transformers:
            devices = hierarchy_service.list_devices(t.transformer_id)
            device_counts[t.transformer_id] = len(devices)

        rows = []
        for t in transformers:
            rows.append({
                "transformer": t.transformer_code,
                "transformer_id": t.transformer_id,
                "devices": device_counts.get(t.transformer_id, 0),
                "status": t.status,
            })

        return rows, TRANSFORMER_COLUMNS

    @app.callback(
        Output("devices-table", "data"),
        Output("devices-table", "columns"),
        Input("page-context", "data"),
        prevent_initial_call=True,
    )
    def populate_transformer_detail(context):
        if not context or context.get("route") != "transformer":
            return no_update, no_update

        transformer_id = context.get("transformer_id")
        devices = hierarchy_service.list_devices(transformer_id)

        rows = []
        for d in devices:
            rows.append({
                "device": d.device_code,
                "device_id": d.device_id,
                "status": d.status,
            })

        return rows, DEVICE_COLUMNS

    # Row-click navigation. dash_table has no non-markdown way to render a
    # cell as a link, and markdown-presentation links are hardcoded by
    # dash_table to target="_blank" (breaking in-app navigation) — so these
    # tables render plain text and a click on the identity column navigates
    # via `url.pathname`, same mechanism as the cascading selector below.

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("plants-table", "active_cell"),
        State("plants-table", "data"),
        prevent_initial_call=True,
    )
    def navigate_from_plants_table(active_cell, rows):
        if not active_cell or active_cell.get("column_id") != "plant":
            return no_update
        row = rows[active_cell["row"]]
        return f"/plants/{row['plant_id']}"

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("transformers-table", "active_cell"),
        State("transformers-table", "data"),
        State("page-context", "data"),
        prevent_initial_call=True,
    )
    def navigate_from_transformers_table(active_cell, rows, context):
        if not active_cell or active_cell.get("column_id") != "transformer":
            return no_update
        plant_id = (context or {}).get("plant_id")
        if not plant_id:
            return no_update
        row = rows[active_cell["row"]]
        return f"/plants/{plant_id}/{row['transformer_id']}"

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("devices-table", "active_cell"),
        State("devices-table", "data"),
        prevent_initial_call=True,
    )
    def navigate_from_devices_table(active_cell, rows):
        if not active_cell or active_cell.get("column_id") != "device":
            return no_update
        row = rows[active_cell["row"]]
        return device_href(row["device_id"])

    # The cascading Plant -> Transformer -> Device selector previously had
    # callbacks here, but the component was never rendered by any layout, so
    # every page-context change raised a nonexistent-Output ReferenceError.
    # Removed rather than half-wired; see docs/CODE_AUDIT.md finding 2 for the
    # design decision the real feature still needs.
