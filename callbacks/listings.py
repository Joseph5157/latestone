"""Listing callbacks — populate drill-down tables and the cascading selector."""
from __future__ import annotations

from dash import Input, Output, State, callback, no_update

from callbacks.routing import device_href
from services import hierarchy_service, monitoring_service


PLANT_COLUMNS = [
    {"name": "Plant", "id": "plant", "presentation": "markdown"},
    {"name": "Country", "id": "country"},
    {"name": "Fuel", "id": "fuel"},
    {"name": "Capacity", "id": "capacity"},
    {"name": "Transformers", "id": "transformers", "type": "numeric"},
    {"name": "Devices", "id": "devices", "type": "numeric"},
]

TRANSFORMER_COLUMNS = [
    {"name": "Transformer", "id": "transformer", "presentation": "markdown"},
    {"name": "Devices", "id": "devices", "type": "numeric"},
    {"name": "Status", "id": "status"},
]

DEVICE_COLUMNS = [
    {"name": "Device", "id": "device", "presentation": "markdown"},
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
                "plant": f"[{p.name}](/plants/{p.plant_id})",
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
            href = f"[{t.transformer_code}](/plants/{plant_id}/{t.transformer_id})"
            rows.append({
                "transformer": href,
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
            href = device_href(d.device_id)
            rows.append({
                "device": f"[{d.device_code}]({href})",
                "status": d.status,
            })

        return rows, DEVICE_COLUMNS

    # Cascading hierarchy selector callbacks

    @app.callback(
        Output("hier-plant", "options"),
        Input("page-context", "data"),
        prevent_initial_call=True,
    )
    def populate_plant_dropdown(context):
        plants = hierarchy_service.list_plants()
        return [{"label": p.name, "value": p.plant_id} for p in plants]

    @app.callback(
        Output("hier-transformer", "options"),
        Output("hier-transformer", "disabled"),
        Input("hier-plant", "value"),
        prevent_initial_call=True,
    )
    def populate_transformer_dropdown(plant_id):
        if not plant_id:
            return [], True
        transformers = hierarchy_service.list_transformers(plant_id)
        options = [{"label": t.transformer_code, "value": t.transformer_id} for t in transformers]
        return options, False

    @app.callback(
        Output("hier-device", "options"),
        Output("hier-device", "disabled"),
        Input("hier-transformer", "value"),
        prevent_initial_call=True,
    )
    def populate_device_dropdown(transformer_id):
        if not transformer_id:
            return [], True
        devices = hierarchy_service.list_devices(transformer_id)
        options = [{"label": d.device_code, "value": d.device_id} for d in devices]
        return options, False

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("hier-device", "value"),
        prevent_initial_call=True,
    )
    def navigate_to_device(device_id):
        if not device_id:
            return no_update
        return device_href(device_id)
