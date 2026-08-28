"""Device Administration callbacks — populate table and handle navigation.

Pattern matches listings.py: module-level pure functions for building rows
and handling navigation targets; `register()` wires them up.
"""
from __future__ import annotations

import logging

from dash import Input, Output, html, no_update

from components.status_panels import error_panel
from routes import device_href
from services import (
    device_scope, hierarchy_service, monitoring_service, prototype_assignments,
)
from components.freshness_badge import format_age
from services.monitoring_service import reading_age, severity_rank

logger = logging.getLogger(__name__)

# Column spec — the callback replaces these on first fire; the page layout
# carries the same spec so the first paint agrees with the callback.
DEVICE_ADMIN_COLUMNS = [
    {"name": "Device", "id": "device"},
    {"name": "Plant", "id": "plant"},
    {"name": "Transformer", "id": "transformer"},
    {"name": "Status", "id": "status"},
    {"name": "Data", "id": "freshness"},
    {"name": "Last reading", "id": "last_reading"},
    {"name": "Technician", "id": "technician"},
    {"name": "Actions", "id": "actions", "presentation": "markdown"},
]

# Markdown action links — dash_table renders markdown cells
_VIEW_LINK = "[View](#)"
_ASSIGN_LINK = "[Assign](#)"
_MANAGE_LINK = "[Manage](#)"


def _format_status(status: str) -> str:
    """Human-readable status label."""
    return status.capitalize() if status else "—"


def build_device_admin_rows(
    devices, health, assignments: dict[str, str] | None = None, *, now=None
) -> list[dict]:
    """One row per device, with freshness and action links.

    Actions:
    - View: navigates to device dashboard
    - Assign: opens assignment drawer (asset + technician)
    - Manage: opens device management drawer (Program RTL, Forwarding, Deactivate)

    `assignments` is device_id -> technician username, fetched once in bulk
    rather than per row. `now` is the render instant, threaded in so the age
    column and the freshness state beside it answer the same "now".

    Freshness is derived from the shared `FleetHealth` object — the same
    definition the Fleet overview card uses — so the admin table's freshness
    labels cannot disagree with the plant table's. One fleet-wide fetch, not
    one per device.
    """
    rows = []
    assignments = assignments or {}
    for d in devices:
        rollup = health.devices.get(d.device_id)
        last_updated = health.device_last_updated.get(d.device_id)
        # No readings at all is an administrative fact, not a missing value:
        # an em dash here would read as a rendering gap.
        last_reading = (
            format_age(reading_age(last_updated, now)) if last_updated else "No readings"
        )
        freshness_label = rollup.label("metrics") if rollup else "No data"
        state_value = rollup.state.value if rollup else "no_data"
        rows.append({
            "id": d.device_id,
            "device": d.device_code,
            "plant": d.plant_name,
            "transformer": d.transformer_code,
            "status": _format_status(d.status),
            "freshness": freshness_label,
            "last_reading": last_reading,
            # Stated, never blank: an empty cell cannot be told apart from a
            # failed lookup, and unassigned RTLs are the queue Administration
            # exists to clear.
            "technician": assignments.get(d.device_id) or "Unassigned",
            "actions": f"{_VIEW_LINK} {_ASSIGN_LINK} {_MANAGE_LINK}",
            "_state": state_value,
            "_severity": severity_rank(rollup.state) if rollup else 2,
        })
    return rows


#: The columns the toolbar's search looks at: the three an administrator
#: recognises a device by. Deliberately not every key on the row — `_state`
#: and the action markdown are identical on most rows, so matching them would
#: return the table for a term visible nowhere on screen.
#: `last_reading` is deliberately absent: "2h 17m" renders a timestamp, so
#: matching it would filter on how long the page had been open.
SEARCHABLE_COLUMNS = ("device", "plant", "transformer", "technician")


def filter_device_rows(rows: list[dict], search, status) -> list[dict]:
    """Apply the toolbar's search and Status filter to already-built rows.

    Filtering happens here rather than in SQL because the rows are already in
    memory for the render — the table is the whole device list, not a page of
    it — and a second query would let the table and its summary line disagree
    about which devices exist.
    """
    term = (search or "").strip().casefold()
    wanted = (status or "all").casefold()

    def matches(row: dict) -> bool:
        if term and not any(
            term in str(row.get(column, "")).casefold() for column in SEARCHABLE_COLUMNS
        ):
            return False
        if wanted != "all" and str(row.get("status", "")).casefold() != wanted:
            return False
        return True

    return [row for row in rows if matches(row)]


def device_admin_summary(shown: int, total: int, active: int, inactive: int) -> str:
    """The line under the toolbar, honest about filtering.

    The active/inactive split always describes the whole fleet, never the
    filtered subset: an administrator reading "118 active" after typing a
    search term would otherwise believe the fleet had shrunk.
    """
    if shown == 0:
        return (
            f"No devices match this filter — {total} devices, "
            f"{active} active, {inactive} inactive"
        )
    lead = f"{total} devices" if shown == total else f"Showing {shown} of {total} devices"
    return f"{lead} — {active} active, {inactive} inactive"


def empty_state(shown: int):
    """The "no rows" message, or None when there are rows.

    A real element rather than CSS: dash_table renders only the header table
    when a table has no rows, so there is no empty `<tbody>` for a `::after`
    to attach to. Distinct from `error_panel()` — this one means "we looked
    and there are none", not "we could not load this".
    """
    if shown:
        return None
    return html.P("No results", className="entity-table-empty")


def device_row_target(active_cell) -> str | None:
    """The device dashboard URL for the clicked row, or None."""
    if not active_cell or active_cell.get("column_id") != "device":
        return None
    device_id = active_cell.get("row_id") or None
    if not device_id:
        return None
    return device_href(device_id)


def register(app) -> None:
    """Register device administration callbacks on the Dash app."""

    @app.callback(
        Output("device-admin-table", "data"),
        Output("device-admin-table", "columns"),
        Output("device-admin-error", "children"),
        Output("device-admin-summary", "children"),
        Output("device-admin-empty", "children"),
        Input("page-context", "data"),
        Input("device-admin-search", "value"),
        Input("device-admin-status-filter", "value"),
        prevent_initial_call=True,
    )
    def populate_device_admin(context, search, status):
        if not context or context.get("route") != "admin_devices":
            return (no_update,) * 5

        rendered_at = monitoring_service._now()
        result: dict = {}

        def build():
            devices = hierarchy_service.list_all_devices()
            # Administration surface: the device admin table is
            # administrator-only by ROUTE_POLICY, so it is deliberately
            # unrestricted rather than resolving a caller scope — same
            # ruling as device_assign.py/device_register.py.
            health = monitoring_service.get_fleet_health(
                rendered_at, scope=device_scope.UNRESTRICTED
            )
            # One bulk lookup for the whole table, not one per row.
            assignments = prototype_assignments.assigned_technicians()
            rows = filter_device_rows(
                build_device_admin_rows(devices, health, assignments, now=rendered_at),
                search,
                status,
            )
            result["rows"] = rows
            result["total"] = len(devices)
            result["active"] = sum(1 for d in devices if d.status == "active")
            result["inactive"] = sum(1 for d in devices if d.status != "active")
            return rows

        try:
            rows = build()
        except Exception:
            logger.exception("Failed to load device administration data")
            # The error panel explains the empty table; a "No results"
            # beside it would claim the fleet is empty when the read failed.
            return [], DEVICE_ADMIN_COLUMNS, error_panel(), "", None

        summary = device_admin_summary(
            len(rows), result["total"], result["active"], result["inactive"]
        )
        return rows, DEVICE_ADMIN_COLUMNS, None, summary, empty_state(len(rows))

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
