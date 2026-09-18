"""Assignments page callbacks — populate table and handle navigation.

ADMIN-ASSIGN-1: a technician workload roster plus the SAME per-device
Assign/Manage table Device Management already offers. Row-building is
reused verbatim from `callbacks.device_admin` (`build_device_admin_rows`) —
this module adds a roster view on top, never a second row-building
implementation. The Assign and Manage drawers are the shared ones too
(ADR-016's "two openers, one drawer" — Device Management's table is one
opener, this one is a third and fourth, for the two drawers respectively).
"""
from __future__ import annotations

import logging
from collections import Counter

from dash import Input, Output, State, no_update

from callbacks.device_admin import (
    DEVICE_ADMIN_COLUMNS,
    build_device_admin_rows,
    device_row_target,
)
from callbacks.device_assign import assign_drawer_open_state, find_device_row
from components.admin_summary import admin_summary_cards
from components.assign_device_drawer import (
    ASSIGN_CLOSE_BTN,
    ASSIGN_DEVICE_ID,
    ASSIGN_DRAWER_ID,
    ASSIGN_RESULT_ID,
    ASSIGN_TECHNICIAN_ID,
)
from components.device_manage_drawer import (
    MANAGE_ACTION_STORE_ID,
    MANAGE_DEVICE_ID,
    MANAGE_DRAWER_ID,
    PROGRAM_RTL_TRANSFORMER_ID,
    PROGRAM_RTL_UID_ID,
)
from components.status_panels import error_panel
from pages.admin_assignments import EMPTY_ID, TABLE_ID, WORKLOAD_TABLE_ID
from services import device_scope, hierarchy_service, monitoring_service, prototype_assignments
from services.action_guard import require_capability
from services.admin_overview_service import get_admin_overview
from services.auth_service import current_identity
from services.authorization import AuthorizationError, MANAGE_DEVICES
from services.prototype_users import get_technicians

logger = logging.getLogger(__name__)

#: Re-exported under this module's own name so `pages/admin_assignments.py`'s
#: duplicated column list has one thing to be tested against — the SAME
#: constant `callbacks.device_admin` already declares, not a second copy of
#: the nine-column spec.
DEVICE_TABLE_COLUMNS = DEVICE_ADMIN_COLUMNS


def build_technician_workload_rows(
    technicians: list[dict], assignments: dict[str, str]
) -> list[dict]:
    """One row per active technician, most-loaded first.

    `assignments` is device_id -> username (the same bulk lookup
    `build_device_admin_rows` already takes), counted once with `Counter`
    rather than one `list_devices_for_technician` query per technician — the
    same "one bulk read, not N" discipline `assigned_technicians()` itself
    documents.

    A technician with zero current assignments still gets a row (count 0):
    the roster's whole purpose is workload visibility, and an idle
    technician is exactly the fact an admin rebalancing load needs to see.
    """
    counts = Counter(assignments.values())
    rows = [
        {
            "id": t["username"],
            "technician": t["username"],
            "count": counts.get(t["username"], 0),
        }
        for t in technicians
    ]
    rows.sort(key=lambda r: (-r["count"], r["technician"]))
    return rows


def _device_sort_key(row: dict) -> tuple:
    """Unassigned first (the actionable queue), then grouped by technician,
    then by device code within each technician — so scanning top-to-bottom
    tells the assignment story directly, the same ordering rationale
    `admin_overview_service`'s unassigned-sample already uses for its own
    list."""
    technician = row.get("technician", "Unassigned")
    return (technician != "Unassigned", technician, row.get("device", ""))


def register(app) -> None:
    """Register Assignments page callbacks on the Dash app."""

    @app.callback(
        Output(WORKLOAD_TABLE_ID, "data"),
        Output(TABLE_ID, "data"),
        Output(TABLE_ID, "columns"),
        Output("admin-assignments-error", "children"),
        Output("admin-assignments-summary", "children"),
        Output(EMPTY_ID, "children"),
        Input("page-context", "data"),
        prevent_initial_call=True,
    )
    def populate_admin_assignments(context):
        if not context or context.get("route") != "admin_assignments":
            return (no_update,) * 6

        # P0-4 (AUTH-HARDEN-1), same lesson as callbacks/device_admin.py:
        # admin_assignments is Administrator-only by ROUTE_POLICY, but this
        # callback answers whoever invokes it directly. Reuses MANAGE_DEVICES
        # rather than a new capability — this page's ROUTE_POLICY entry is
        # the SAME _ADMIN_ONLY set admin_devices already uses, so a second,
        # identically-scoped capability would name nothing new.
        try:
            require_capability(current_identity(), MANAGE_DEVICES)
        except AuthorizationError:
            logger.warning("Assignments data refused: not an administrator.")
            return [], [], DEVICE_TABLE_COLUMNS, error_panel(), None, None

        try:
            rendered_at = monitoring_service._now()
            devices = hierarchy_service.list_all_devices(include_inactive=True)
            health = monitoring_service.get_fleet_health(
                rendered_at, scope=device_scope.UNRESTRICTED
            )
            assignments = prototype_assignments.assigned_technicians()
            technicians = get_technicians()

            workload_rows = build_technician_workload_rows(technicians, assignments)
            device_rows = sorted(
                build_device_admin_rows(devices, health, assignments, now=rendered_at),
                key=_device_sort_key,
            )
            summary = admin_summary_cards(get_admin_overview(rendered_at))
        except Exception:
            logger.exception("Failed to load assignments data")
            return [], [], DEVICE_TABLE_COLUMNS, error_panel(), None, None

        return workload_rows, device_rows, DEVICE_TABLE_COLUMNS, None, summary, None

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input(TABLE_ID, "active_cell"),
        prevent_initial_call=True,
    )
    def navigate_from_assignment_devices_table(active_cell):
        return device_row_target(active_cell) or no_update

    # Assign column — a second opener for the shared assignment drawer.
    # `assign_drawer_open_state`/`find_device_row` are reused verbatim from
    # callbacks/device_assign.py: same technician options, same pre-selected
    # technician, same empty state — one assignment workflow, not two.
    @app.callback(
        Output(ASSIGN_DRAWER_ID, "style", allow_duplicate=True),
        Output(ASSIGN_DEVICE_ID, "data", allow_duplicate=True),
        Output("assign-drawer-device-code", "children", allow_duplicate=True),
        Output("assign-drawer-current-transformer", "children", allow_duplicate=True),
        Output("assign-drawer-current-plant", "children", allow_duplicate=True),
        Output(ASSIGN_TECHNICIAN_ID, "options", allow_duplicate=True),
        Output(ASSIGN_TECHNICIAN_ID, "value", allow_duplicate=True),
        Output("assign-technician-empty", "children", allow_duplicate=True),
        Output("assign-technician-empty", "style", allow_duplicate=True),
        Output(ASSIGN_RESULT_ID, "children", allow_duplicate=True),
        Output(ASSIGN_CLOSE_BTN, "children", allow_duplicate=True),
        Input(TABLE_ID, "active_cell"),
        State(TABLE_ID, "data"),
        prevent_initial_call=True,
    )
    def open_assign_drawer_from_assignments(active_cell, table_data):
        try:
            require_capability(current_identity(), MANAGE_DEVICES)
        except AuthorizationError:
            return (no_update,) * 11

        if not active_cell or active_cell.get("column_id") != "assign":
            return (no_update,) * 11

        row = find_device_row(table_data, active_cell.get("row_id"))
        state = assign_drawer_open_state(row)
        if state is None:
            return (no_update,) * 11
        return (*state, "", "Cancel")

    # Manage column — a third opener for the one shared drawer (ADR-016's
    # "two openers, one drawer" — device-admin-table, the device page's own
    # button — becomes three across the app, this page's fourth).
    @app.callback(
        Output(MANAGE_DRAWER_ID, "style", allow_duplicate=True),
        Output(MANAGE_DEVICE_ID, "data", allow_duplicate=True),
        Output(MANAGE_ACTION_STORE_ID, "data", allow_duplicate=True),
        Output("manage-drawer-device-code", "children", allow_duplicate=True),
        Output("manage-drawer-transformer", "children", allow_duplicate=True),
        Output("manage-drawer-plant", "children", allow_duplicate=True),
        Output("manage-program-panel", "style", allow_duplicate=True),
        Output("manage-forwarding-panel", "style", allow_duplicate=True),
        Output("manage-deactivate-panel", "style", allow_duplicate=True),
        Output("manage-action-menu", "style", allow_duplicate=True),
        Output(PROGRAM_RTL_UID_ID, "value", allow_duplicate=True),
        Output(PROGRAM_RTL_TRANSFORMER_ID, "value", allow_duplicate=True),
        Input(TABLE_ID, "active_cell"),
        State(TABLE_ID, "data"),
        prevent_initial_call=True,
    )
    def open_manage_drawer_from_assignments(active_cell, table_data):
        if not active_cell or active_cell.get("column_id") != "manage":
            return (no_update,) * 12

        row_id = active_cell.get("row_id")
        if not row_id:
            return (no_update,) * 12

        row = next((r for r in (table_data or []) if r.get("id") == row_id), None)
        if not row:
            return (no_update,) * 12

        return (
            {"display": "block"},           # show drawer
            row_id,                          # store device_id
            "menu",                          # start at action menu
            row.get("device", "—"),          # device code
            row.get("transformer", "—"),     # transformer
            row.get("plant", "—"),           # plant
            {"display": "none"},            # program panel hidden
            {"display": "none"},            # forwarding panel hidden
            {"display": "none"},            # deactivate panel hidden
            {"display": "block"},           # menu visible
            row.get("device", ""),           # pre-fill UID
            row.get("transformer", ""),      # pre-fill transformer name
        )
