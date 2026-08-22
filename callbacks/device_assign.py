"""Device Assignment callbacks — open drawer, cascade, technician selection, mock submit.

Asset (device -> transformer) assignment is frontend-only: the mock adapter
stores the latest assignment in memory and does not write to any database.
It is intentionally not persisted — it is redundant with
devices.transformer_id, which this callback does not touch.

Technician assignment is persisted (DB-3) via
services/prototype_assignments.py, backed by
plant_monitoring.user_device_assignments. Technician *options* come from
the shared prototype user store, services/prototype_users.py.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update, html

from components.assign_device_drawer import (
    ASSIGN_DRAWER_ID,
    ASSIGN_DEVICE_ID,
    ASSIGN_PLANT_ID,
    ASSIGN_TRANSFORMER_ID,
    ASSIGN_TECHNICIAN_ID,
    ASSIGN_CONFIRM_BTN,
    ASSIGN_CANCEL_BTN,
)
from routes import parse_assign_request
from services import device_scope, hierarchy_service, prototype_assignments
from services.prototype_users import get_technician_options

logger = logging.getLogger(__name__)

#: Empty-state styling for the technician dropdown, kept beside the text it
#: goes with so the two cannot drift apart between trigger paths.
_NO_TECHNICIANS_TEXT = (
    "No technicians available. Add a technician in User Administration."
)
_NO_TECHNICIANS_STYLE = {
    "display": "block",
    "color": "var(--color-muted)",
    "fontStyle": "italic",
    "fontSize": "var(--fs-meta)",
}

# In-memory store for prototype asset assignments: device_id -> transformer_id
_mock_assignments: dict[str, str] = {}


def get_mock_assignment(device_id: str) -> str | None:
    """Read the mock asset assignment for a device (for testing)."""
    return _mock_assignments.get(device_id)


def clear_mock_assignments() -> None:
    """Reset the mock asset assignment store (for testing)."""
    _mock_assignments.clear()


def find_device_row(table_data, device_id: str | None) -> dict | None:
    """The Device Management row for `device_id`, or None.

    The resolution step for an identifier that arrived from the browser. It is
    matched against rows already rendered on this page rather than trusted:
    an `?assign=` value naming something that is not in the table opens
    nothing, so a hand-edited URL cannot address a device the page is not
    showing. No SQL is reached for here — the row the drawer needs is already
    on screen.
    """
    if not device_id:
        return None
    return next(
        (r for r in (table_data or []) if r.get("id") == device_id), None
    )


def assign_drawer_open_state(row: dict | None):
    """The assignment drawer's nine outputs for `row`, or None to open nothing.

    THE one place the drawer's opening state is built. Both trigger paths —
    clicking Assign in the Device Management table, and arriving from the
    Fleet Overview's Unassigned RTLs panel via `?assign=` — go through here,
    so the deep link cannot become a second, subtly different assignment
    workflow: same technician options, same pre-selected technician, same
    empty state, same device context.

    Returns None when there is nothing to open — no row, or a row whose
    actions do not include Assign — which each caller turns into `no_update`.
    """
    if not row:
        return None
    if "Assign" not in (row.get("actions") or ""):
        return None

    tech_options = get_technician_options()
    current_technician = prototype_assignments.get_assigned_technician(row.get("id"))

    if tech_options:
        empty_text = ""
        empty_style = {"display": "none"}
    else:
        empty_text = _NO_TECHNICIANS_TEXT
        empty_style = _NO_TECHNICIANS_STYLE

    return (
        {"display": "block"},            # show drawer
        row.get("id"),                   # store device_id
        row.get("device", "—"),          # device code
        row.get("transformer", "—"),     # transformer
        row.get("plant", "—"),           # plant
        tech_options,                    # technician dropdown options
        current_technician,              # pre-select current technician
        empty_text,                      # empty state text
        empty_style,                     # empty state visibility
    )


def _plant_options() -> list[dict]:
    # Administration surface: the device-management population is deliberately
    # fleet-wide, like list_all_devices (spec §4.6). ROUTE_POLICY gates this page
    # administrator-only. Stated explicitly rather than omitted, per invariant 8.
    return [
        {"label": p.name, "value": p.plant_id}
        for p in hierarchy_service.list_plants(scope=device_scope.UNRESTRICTED)
    ]


def _transformer_options(plant_id: str) -> list[dict]:
    if not plant_id:
        return []
    # Administration surface: the device-management population is deliberately
    # fleet-wide, like list_all_devices (spec §4.6). ROUTE_POLICY gates this page
    # administrator-only. Stated explicitly rather than omitted, per invariant 8.
    return [
        {"label": t.transformer_code, "value": t.transformer_id}
        for t in hierarchy_service.list_transformers(
            plant_id, scope=device_scope.UNRESTRICTED
        )
    ]


def register(app) -> None:
    """Register device assignment callbacks on the Dash app."""

    @app.callback(
        Output(ASSIGN_DRAWER_ID, "style"),
        Output(ASSIGN_DEVICE_ID, "data"),
        Output("assign-drawer-device-code", "children"),
        Output("assign-drawer-current-transformer", "children"),
        Output("assign-drawer-current-plant", "children"),
        Output(ASSIGN_TECHNICIAN_ID, "options"),
        Output(ASSIGN_TECHNICIAN_ID, "value"),
        Output("assign-technician-empty", "children"),
        Output("assign-technician-empty", "style"),
        Input("device-admin-table", "active_cell"),
        State("device-admin-table", "data"),
        prevent_initial_call=True,
    )
    def open_assign_drawer(active_cell, table_data):
        """Open the assignment drawer when Assign is clicked."""
        if not active_cell or active_cell.get("column_id") != "actions":
            return (no_update,) * 9

        row = find_device_row(table_data, active_cell.get("row_id"))
        return assign_drawer_open_state(row) or (no_update,) * 9

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
        Input("device-admin-table", "data"),
        State("url", "search"),
        prevent_initial_call=True,
    )
    def open_assign_drawer_from_url(table_data, search):
        """Open the drawer for a device named by an `?assign=` deep link.

        The Fleet Overview's Unassigned RTLs panel (ADMIN-3) links here rather
        than carrying its own drawer. This is the arrival half of that handoff,
        and it shares `assign_drawer_open_state` with the click path above, so
        there is one assignment workflow rather than two.

        Triggered by the table's `data` rather than by the URL directly: the
        drawer and the row it describes both belong to this page, and firing
        once the table has populated is what guarantees they exist. The device
        is then resolved against those rows, so an unknown identifier opens
        nothing.
        """
        row = find_device_row(table_data, parse_assign_request(search))
        return assign_drawer_open_state(row) or (no_update,) * 9

    @app.callback(
        Output(ASSIGN_DRAWER_ID, "style", allow_duplicate=True),
        Input(ASSIGN_CANCEL_BTN, "n_clicks"),
        Input("assign-drawer-overlay", "n_clicks"),
        prevent_initial_call=True,
    )
    def close_assign_drawer(cancel_clicks, overlay_clicks):
        """Close the assignment drawer without making changes."""
        return {"display": "none"}

    @app.callback(
        Output(ASSIGN_TRANSFORMER_ID, "options"),
        Output(ASSIGN_TRANSFORMER_ID, "disabled"),
        Input(ASSIGN_PLANT_ID, "value"),
        prevent_initial_call=True,
    )
    def _cascade_transformers(plant_id):
        """Populate transformer dropdown based on selected plant."""
        try:
            options = _transformer_options(plant_id)
            return options, not options
        except Exception:
            logger.exception("Failed to cascade transformers for %r", plant_id)
            return [], True

    @app.callback(
        Output(ASSIGN_DRAWER_ID, "style", allow_duplicate=True),
        Output(ASSIGN_DEVICE_ID, "data", allow_duplicate=True),
        Input(ASSIGN_CONFIRM_BTN, "n_clicks"),
        State(ASSIGN_DEVICE_ID, "data"),
        State(ASSIGN_PLANT_ID, "value"),
        State(ASSIGN_TRANSFORMER_ID, "value"),
        State(ASSIGN_TECHNICIAN_ID, "value"),
        prevent_initial_call=True,
    )
    def confirm_assignment(n_clicks, device_id, plant_id, transformer_id, technician):
        """Prototype confirm — stores in memory, no database write."""
        if not n_clicks or not device_id:
            return no_update, no_update

        # Store asset assignment if transformer selected
        if transformer_id:
            _mock_assignments[device_id] = transformer_id
            logger.info(
                "Prototype asset assignment: device %s -> transformer %s",
                device_id, transformer_id,
            )

        # Store technician assignment (persisted, DB-3)
        if technician:
            try:
                prototype_assignments.assign_technician(device_id, technician)
                logger.info(
                    "Technician assignment: device %s -> technician %s",
                    device_id, technician,
                )
            except ValueError:
                logger.exception(
                    "Failed to assign technician %s to device %s",
                    technician, device_id,
                )
        elif prototype_assignments.get_assigned_technician(device_id) is not None:
            # Clear technician assignment if none selected
            prototype_assignments.unassign_technician(device_id)
            logger.info(
                "Technician assignment cleared: device %s",
                device_id,
            )

        # Close the drawer
        return {"display": "none"}, device_id

    @app.callback(
        Output(ASSIGN_PLANT_ID, "options"),
        Input(ASSIGN_DRAWER_ID, "style"),
    )
    def _populate_plants_on_open(style):
        """Populate plant dropdown when drawer opens."""
        if not style or style.get("display") == "none":
            return no_update
        try:
            return _plant_options()
        except Exception:
            logger.exception("Failed to populate plant options for assignment")
            return []
