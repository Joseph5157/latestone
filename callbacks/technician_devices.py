"""Technician Devices page callbacks.

A Technician's own operate-equipment surface (ADR-016): the same rows
`callbacks.listings.build_my_rtls_rows` produces for the Overview page's My
RTLs panel, plus a "Manage" column opening the SAME `device_manage_drawer()`
`callbacks/device_manage.py` already drives from `/admin/devices` and the
device dashboard — a third opener for that one shared drawer, never a copy
of it. No Assign column, no Register button, no Status/Technician column:
this page never offers assignment (ADR-016) and a Technician already knows
these are their own devices.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update

from callbacks.listings import (
    FRESHNESS_SORT_OVERRIDES,
    build_my_rtls_rows,
    device_row_target,
)
from components.device_manage_drawer import (
    MANAGE_ACTION_STORE_ID,
    MANAGE_DEVICE_ID,
    MANAGE_DRAWER_ID,
    PROGRAM_RTL_TRANSFORMER_ID,
    PROGRAM_RTL_UID_ID,
)
from components.entity_table import sort_table_rows
from components.status_panels import empty_data_panel, error_panel
from pages.technician_devices import EMPTY_ID, TABLE_ID, TECHNICIAN_DEVICE_COLUMNS
from services import monitoring_service
from services.action_guard import require_capability
from services.auth_service import current_identity
from services.authorization import AuthorizationError, VIEW_OWN_DEVICES
from services.device_scope import current_device_scope

logger = logging.getLogger(__name__)

#: Same placeholder-link shape as `pages.device_admin._MANAGE_LINK` — the
#: real navigation happens through `active_cell`, never this href, matching
#: the "Row-click navigation" convention `callbacks/listings.py` documents.
_MANAGE_LINK = "[Manage](#)"


def _summary(count: int) -> str:
    noun = "RTL" if count == 1 else "RTLs"
    return f"{count} assigned {noun}."


def register(app) -> None:
    """Register Technician Devices callbacks on the Dash app."""

    @app.callback(
        Output(TABLE_ID, "data"),
        Output(TABLE_ID, "columns"),
        Output("technician-devices-error", "children"),
        Output("technician-devices-summary", "children"),
        Output(EMPTY_ID, "children"),
        Input("page-context", "data"),
        Input(TABLE_ID, "sort_by"),
        prevent_initial_call=True,
    )
    def populate_technician_devices(context, sort_by=None):
        if not context or context.get("route") != "technician_devices":
            return (no_update,) * 5

        # P0-4 (AUTH-HARDEN-1), same lesson as callbacks/device_admin.py and
        # callbacks/user_admin.py: `technician_devices` is Technician-only by
        # ROUTE_POLICY, but this callback answers whoever invokes it
        # directly and the route check only ever guarded the RENDER that
        # built page-context, not this independently-triggerable one.
        user = current_identity()
        try:
            require_capability(user, VIEW_OWN_DEVICES)
        except AuthorizationError:
            logger.warning("Technician devices data refused: not a technician.")
            return [], TECHNICIAN_DEVICE_COLUMNS, error_panel(), "", None

        try:
            scope = current_device_scope()
            rendered_at = monitoring_service._now()
            health = monitoring_service.get_fleet_health(rendered_at, scope=scope)
            rows = sort_table_rows(
                [
                    {**row, "manage": _MANAGE_LINK}
                    for row in build_my_rtls_rows(scope, health)
                ],
                sort_by,
                FRESHNESS_SORT_OVERRIDES,
            )
        except Exception:
            logger.exception("Failed to load technician devices data")
            return [], TECHNICIAN_DEVICE_COLUMNS, error_panel(), "", None

        empty = (
            empty_data_panel("No RTLs are currently assigned to you.")
            if not rows else None
        )
        return rows, TECHNICIAN_DEVICE_COLUMNS, None, _summary(len(rows)), empty

    # Row-click navigation (RTL column) — device_row_target is reused
    # verbatim, the same way navigate_from_my_rtls_table reuses it, so this
    # table and My RTLs can never drift on what counts as the identity
    # column or how a device_id becomes a URL.
    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input(TABLE_ID, "active_cell"),
        prevent_initial_call=True,
    )
    def navigate_from_technician_devices_table(active_cell):
        if not active_cell or active_cell.get("column_id") != "device":
            return no_update
        return device_row_target(active_cell)

    # Manage column — a third opener for the one shared drawer (ADR-016's
    # "two openers, one drawer" becomes three). Identical in shape to
    # callbacks/device_manage.py::open_manage_drawer, just keyed to this
    # table's own id; that existing callback cannot be reused directly
    # because it is keyed to "device-admin-table" specifically.
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
    def open_manage_drawer_from_technician_devices(active_cell, table_data):
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
