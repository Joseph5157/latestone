"""Device Administration callbacks — populate table and handle navigation.

Pattern matches listings.py: module-level pure functions for building rows
and handling navigation targets; `register()` wires them up.
"""
from __future__ import annotations

import logging

from dash import Input, Output, no_update

from components.status_panels import error_panel
from routes import device_href
from services import hierarchy_service, monitoring_service
from services.monitoring_service import severity_rank

logger = logging.getLogger(__name__)

# Column spec — the callback replaces these on first fire; the page layout
# carries the same spec so the first paint agrees with the callback.
DEVICE_ADMIN_COLUMNS = [
    {"name": "Device", "id": "device"},
    {"name": "Plant", "id": "plant"},
    {"name": "Transformer", "id": "transformer"},
    {"name": "Status", "id": "status"},
    {"name": "Data", "id": "freshness"},
    {"name": "Actions", "id": "actions", "presentation": "markdown"},
]

# Markdown action links — dash_table renders markdown cells
_VIEW_LINK = "[View](#)"
_ASSIGN_LINK = "[Assign](#)"
_MANAGE_LINK = "[Manage](#)"


def _format_status(status: str) -> str:
    """Human-readable status label."""
    return status.capitalize() if status else "—"


def build_device_admin_rows(devices, health) -> list[dict]:
    """One row per device, with freshness and action links.

    Actions:
    - View: navigates to device dashboard
    - Assign: opens assignment drawer (asset + technician)
    - Manage: opens device management drawer (Program RTL, Forwarding, Deactivate)

    Freshness is derived from the shared `FleetHealth` object — the same
    definition the Fleet overview card uses — so the admin table's freshness
    labels cannot disagree with the plant table's. One fleet-wide fetch, not
    one per device.
    """
    rows = []
    for d in devices:
        rollup = health.devices.get(d.device_id)
        freshness_label = rollup.label("metrics") if rollup else "No data"
        state_value = rollup.state.value if rollup else "no_data"
        rows.append({
            "id": d.device_id,
            "device": d.device_code,
            "plant": d.plant_name,
            "transformer": d.transformer_code,
            "status": _format_status(d.status),
            "freshness": freshness_label,
            "actions": f"{_VIEW_LINK} {_ASSIGN_LINK} {_MANAGE_LINK}",
            "_state": state_value,
            "_severity": severity_rank(rollup.state) if rollup else 2,
        })
    return rows


def device_row_target(active_cell) -> str | None:
    """The device dashboard URL for the clicked row, or None."""
    if not active_cell or active_cell.get("column_id") != "device":
        return None
    device_id = active_cell.get("row_id") or None
    if not device_id:
        return None
    return device_href(device_id)


def _is_view_action(active_cell) -> bool:
    """True if the clicked action is View."""
    if not active_cell or active_cell.get("column_id") != "actions":
        return False
    return True  # handled by specific callback dispatch


def register(app) -> None:
    """Register device administration callbacks on the Dash app."""

    @app.callback(
        Output("device-admin-table", "data"),
        Output("device-admin-table", "columns"),
        Output("device-admin-error", "children"),
        Output("device-admin-summary", "children"),
        Input("page-context", "data"),
        prevent_initial_call=True,
    )
    def populate_device_admin(context):
        if not context or context.get("route") != "admin_devices":
            return (no_update,) * 4

        rendered_at = monitoring_service._now()
        result: dict = {}

        def build():
            devices = hierarchy_service.list_all_devices()
            health = monitoring_service.get_fleet_health(rendered_at)
            rows = build_device_admin_rows(devices, health)
            result["rows"] = rows
            result["total"] = len(devices)
            result["active"] = sum(1 for d in devices if d.status == "active")
            result["inactive"] = sum(1 for d in devices if d.status != "active")
            return rows

        try:
            rows = build()
        except Exception:
            logger.exception("Failed to load device administration data")
            return [], DEVICE_ADMIN_COLUMNS, error_panel(), ""

        summary = (
            f"{result['total']} devices total — "
            f"{result['active']} active, {result['inactive']} inactive"
        )
        return rows, DEVICE_ADMIN_COLUMNS, None, summary

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("device-admin-table", "active_cell"),
        prevent_initial_call=True,
    )
    def navigate_from_device_admin_table(active_cell):
        """Navigate to device dashboard when View is clicked."""
        if not active_cell or active_cell.get("column_id") != "device":
            return no_update
        target = device_row_target(active_cell)
        return target or no_update

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("device-admin-register-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def navigate_to_register(n_clicks):
        if not n_clicks:
            return no_update
        return "/admin/devices/new"
