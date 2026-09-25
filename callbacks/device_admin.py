"""Device Administration callbacks — populate table and handle navigation.

Pattern matches listings.py: module-level pure functions for building rows
and handling navigation targets; `register()` wires them up.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from dash import Input, Output, html, no_update

from components.entity_table import sort_table_rows
from components.status_panels import error_panel
from routes import device_href
from services import (
    device_scope, hierarchy_service, monitoring_service, prototype_assignments,
)
from components.freshness_badge import format_age
from services.action_guard import require_capability
from services.auth_service import current_identity
from services.authorization import AuthorizationError, MANAGE_DEVICES
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
    # ONE COLUMN PER ACTION. A DataTable's `active_cell` names a cell and
    # says nothing about which markdown link inside it was clicked, so the
    # single "Actions" cell these replace delivered every click to BOTH the
    # assign and the manage callback — `column_id` was identical, and the
    # text checks that tried to tell them apart could not, because every
    # row's markdown was the same literal string.
    #
    # `column_id` is the routing key both callbacks already used; the defect
    # was one cell carrying two actions, not the mechanism. Splitting the
    # cell makes each action addressable without pattern-matching ids or a
    # click-position heuristic.
    {"name": "Assign", "id": "assign", "presentation": "markdown"},
    {"name": "Manage", "id": "manage", "presentation": "markdown"},
]

#: TABLE-SORT-TEXT-1: `entity_table`'s `sort_action="custom"` columns that
#: render one value but must sort by another — Last reading renders a
#: formatted age ("5d 3h" sorts before "8 min" as text) and Data renders a
#: freshness label (sorts A-Z, not by severity). Every other column's
#: rendered value already IS its sort value.
DEVICE_ADMIN_SORT_OVERRIDES = {
    "last_reading": "_age_seconds",
    "freshness": "_severity",
}

#: No real reading is ever this old; a device with none at all must still
#: sort as the worst "Last reading" in either direction, the same rule
#: `_severity`'s NO_DATA=2 already applies to the Data column.
_NO_READING_SORT_AGE_SECONDS = 10**9

# Markdown action links — dash_table renders markdown cells. There is no
# View link: the device name navigates (`navigate_from_device_admin_table`
# on `column_id == "device"`), which is where View already went.
_ASSIGN_LINK = "[Assign](#)"
_MANAGE_LINK = "[Manage](#)"


def _format_status(status: str) -> str:
    """Human-readable status label."""
    return status.capitalize() if status else "—"


#: The Technician filter's value for "no technician". Leading underscore so
#: it can never collide with a real username.
UNASSIGNED = "_unassigned"


def last_reading_band(age) -> str:
    """The Last reading filter band for a reading age (DEVICE-FILTERS-1).

    Readings arrive about every 30 minutes, so under an hour means reporting
    normally. The 24-hour edge matches BR008's ">24 h no data" rule: exactly
    24 hours is still "1–24 hours".
    """
    if age is None:
        return "none"
    if age < timedelta(hours=1):
        return "lt1h"
    if age <= timedelta(hours=24):
        return "1to24h"
    return "gt24h"


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
        age = reading_age(last_updated, now) if last_updated else None
        # No readings at all is an administrative fact, not a missing value:
        # an em dash here would read as a rendering gap.
        last_reading = format_age(age) if age is not None else "No readings"
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
            "assign": _ASSIGN_LINK,
            "manage": _MANAGE_LINK,
            "_state": state_value,
            "_severity": severity_rank(rollup.state) if rollup else 2,
            # TABLE-SORT-TEXT-1: the real sort key behind "last_reading"'s
            # formatted text.
            "_age_seconds": (
                age.total_seconds() if age is not None
                else _NO_READING_SORT_AGE_SECONDS
            ),
            # Filter keys (DEVICE-FILTERS-1). Ids, not labels: transformer
            # codes repeat across plants.
            "_plant_id": d.plant_id,
            "_transformer_id": d.transformer_id,
            "_reading_band": last_reading_band(age),
        })
    return rows


#: The columns the toolbar's search looks at: the three an administrator
#: recognises a device by. Deliberately not every key on the row — `_state`
#: and the action markdown are identical on most rows, so matching them would
#: return the table for a term visible nowhere on screen.
#: `last_reading` is deliberately absent: "2h 17m" renders a timestamp, so
#: matching it would filter on how long the page had been open.
SEARCHABLE_COLUMNS = ("device", "plant", "transformer", "technician")


def _chosen(value) -> str | None:
    """A dropdown value that filters, or None for "All" / cleared."""
    return None if value in (None, "", "all") else value


def filter_device_rows(
    rows: list[dict],
    search,
    status,
    *,
    plant=None,
    transformer=None,
    freshness=None,
    technician=None,
    reading=None,
) -> list[dict]:
    """Apply the toolbar's filters to already-built rows.

    Filtering happens here rather than in SQL because the rows are already in
    memory for the render — the table is the whole device list, not a page of
    it — and a second query would let the table and its summary line disagree
    about which devices exist.

    Every column filter is optional; None or "all" means no filter.
    """
    term = (search or "").strip().casefold()
    wanted = (status or "all").casefold()
    plant, transformer = _chosen(plant), _chosen(transformer)
    freshness, technician, reading = _chosen(freshness), _chosen(technician), _chosen(reading)

    # Changing Plant clears Transformer, but the table can render once with
    # the previous plant's transformer still selected. A transformer outside
    # the chosen plant is that leftover, not a request for an empty table.
    if plant and transformer and not any(
        r.get("_plant_id") == plant and r.get("_transformer_id") == transformer
        for r in rows
    ):
        transformer = None

    def matches(row: dict) -> bool:
        if term and not any(
            term in str(row.get(column, "")).casefold() for column in SEARCHABLE_COLUMNS
        ):
            return False
        if wanted != "all" and str(row.get("status", "")).casefold() != wanted:
            return False
        if plant and row.get("_plant_id") != plant:
            return False
        if transformer and row.get("_transformer_id") != transformer:
            return False
        if freshness and row.get("_state") != freshness:
            return False
        if technician:
            holder = row.get("technician")
            if technician == UNASSIGNED:
                if holder not in (None, "", "Unassigned"):
                    return False
            elif holder != technician:
                return False
        if reading and row.get("_reading_band") != reading:
            return False
        return True

    return [row for row in rows if matches(row)]


def plant_filter_options(plants) -> list[dict]:
    """Plant filter choices, by name. "All" is the dropdown's cleared state."""
    return [
        {"label": p.name, "value": p.plant_id}
        for p in sorted(plants, key=lambda p: p.name.casefold())
    ]


def transformer_filter_options(transformers) -> list[dict]:
    """Transformer filter choices for one plant, by code."""
    return [
        {"label": t.transformer_code, "value": t.transformer_id}
        for t in sorted(transformers, key=lambda t: t.transformer_code.casefold())
    ]


def technician_filter_options(assignments: dict[str, str]) -> list[dict]:
    """All, Unassigned, then every technician who currently holds a device."""
    technicians = sorted(set(filter(None, assignments.values())), key=str.casefold)
    return [
        {"label": "All", "value": "all"},
        {"label": "Unassigned", "value": UNASSIGNED},
        *({"label": name, "value": name} for name in technicians),
    ]


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
        Input("device-admin-plant-filter", "value"),
        Input("device-admin-transformer-filter", "value"),
        Input("device-admin-data-filter", "value"),
        Input("device-admin-technician-filter", "value"),
        Input("device-admin-reading-filter", "value"),
        Input("device-admin-table", "sort_by"),
        prevent_initial_call=True,
    )
    def populate_device_admin(
        context, search, status,
        plant=None, transformer=None, freshness="all", technician="all", reading="all",
        sort_by=None,
    ):
        if not context or context.get("route") != "admin_devices":
            return (no_update,) * 5

        # P0-4 (AUTH-HARDEN-1). `admin_devices` is administrator-only by
        # ROUTE_POLICY, but this callback answers whoever invokes it directly
        # and the route check only ever guarded the RENDER that built
        # page-context, not this independently-triggerable one. Without this,
        # a forged {"route": "admin_devices"} handed the full 120-device
        # roster — including which technician is assigned to each — to any
        # authenticated role.
        try:
            require_capability(current_identity(), MANAGE_DEVICES)
        except AuthorizationError:
            logger.warning("Device administration data refused: not an administrator.")
            return [], DEVICE_ADMIN_COLUMNS, error_panel(), "", None

        rendered_at = monitoring_service._now()
        result: dict = {}

        def build():
            # `include_inactive=True` is requested HERE, not by moving the
            # shared default. This page advertises an Active/Inactive filter
            # (pages/device_admin.py) and states an active/inactive split in
            # its summary line, so it is the caller that needs the wider
            # population — while `db/live_simulator.py`, the two seeds and
            # `callbacks/listings.py` all rely on the active-only default and
            # must keep it.
            #
            # Without this the filter was correct code over a population that
            # could not contain what it was asked for: choosing "Inactive"
            # returned nothing, and the summary's inactive count was
            # structurally always 0.
            devices = hierarchy_service.list_all_devices(include_inactive=True)
            # Administration surface: the device admin table is
            # administrator-only by ROUTE_POLICY, so it is deliberately
            # unrestricted rather than resolving a caller scope — same
            # ruling as device_assign.py/device_register.py.
            health = monitoring_service.get_fleet_health(
                rendered_at, scope=device_scope.UNRESTRICTED
            )
            # One bulk lookup for the whole table, not one per row.
            assignments = prototype_assignments.assigned_technicians()
            rows = sort_table_rows(
                filter_device_rows(
                    build_device_admin_rows(devices, health, assignments, now=rendered_at),
                    search,
                    status,
                    plant=plant,
                    transformer=transformer,
                    freshness=freshness,
                    technician=technician,
                    reading=reading,
                ),
                sort_by,
                DEVICE_ADMIN_SORT_OVERRIDES,
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
        Output("device-admin-plant-filter", "options"),
        Output("device-admin-technician-filter", "options"),
        Input("page-context", "data"),
        prevent_initial_call=True,
    )
    def _load_filter_options(context):
        """Plant and Technician choices, once per page render.

        Separate from the table so changing a filter does not rebuild its own
        options. Independently invokable, so it re-checks the capability:
        plant names and who holds devices are administration data.
        """
        if not context or context.get("route") != "admin_devices":
            return no_update, no_update
        try:
            require_capability(current_identity(), MANAGE_DEVICES)
        except AuthorizationError:
            return [], technician_filter_options({})
        try:
            plants = hierarchy_service.list_plants(scope=device_scope.UNRESTRICTED)
            assignments = prototype_assignments.assigned_technicians()
        except Exception:
            logger.exception("Failed to load device filter options")
            return [], technician_filter_options({})
        return plant_filter_options(plants), technician_filter_options(assignments)

    @app.callback(
        Output("device-admin-transformer-filter", "options"),
        Output("device-admin-transformer-filter", "disabled"),
        Output("device-admin-transformer-filter", "value"),
        Input("device-admin-plant-filter", "value"),
        prevent_initial_call=True,
    )
    def _load_transformer_options(plant_id):
        """The chosen plant's transformers; cleared whenever Plant changes."""
        if not plant_id:
            return [], True, None
        try:
            require_capability(current_identity(), MANAGE_DEVICES)
        except AuthorizationError:
            return [], True, None
        try:
            transformers = hierarchy_service.list_transformers(
                plant_id, scope=device_scope.UNRESTRICTED
            )
        except Exception:
            logger.exception("Failed to load transformers for %r", plant_id)
            return [], True, None
        options = transformer_filter_options(transformers)
        return options, not options, None

    @app.callback(
        Output("device-admin-search", "value"),
        Output("device-admin-status-filter", "value"),
        Output("device-admin-plant-filter", "value"),
        Output("device-admin-data-filter", "value"),
        Output("device-admin-technician-filter", "value"),
        Output("device-admin-reading-filter", "value"),
        Input("device-admin-clear-filters", "n_clicks"),
        prevent_initial_call=True,
    )
    def _clear_filters(n_clicks):
        """Every filter back to its default. Clearing Plant clears
        Transformer through `_load_transformer_options`."""
        if not n_clicks:
            return (no_update,) * 6
        return "", "all", None, "all", "all", "all"

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
