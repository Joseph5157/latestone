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
from services import hierarchy_service, prototype_assignments
from services.prototype_users import get_technician_options

logger = logging.getLogger(__name__)

# In-memory store for prototype asset assignments: device_id -> transformer_id
_mock_assignments: dict[str, str] = {}


def get_mock_assignment(device_id: str) -> str | None:
    """Read the mock asset assignment for a device (for testing)."""
    return _mock_assignments.get(device_id)


def clear_mock_assignments() -> None:
    """Reset the mock asset assignment store (for testing)."""
    _mock_assignments.clear()


def _plant_options() -> list[dict]:
    return [
        {"label": p.name, "value": p.plant_id}
        for p in hierarchy_service.list_plants()
    ]


def _transformer_options(plant_id: str) -> list[dict]:
    if not plant_id:
        return []
    return [
        {"label": t.transformer_code, "value": t.transformer_id}
        for t in hierarchy_service.list_transformers(plant_id)
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

        row_id = active_cell.get("row_id")
        if not row_id:
            return (no_update,) * 9

        # Check if this is an Assign action (not View or Manage)
        row = next((r for r in (table_data or []) if r.get("id") == row_id), None)
        if not row:
            return (no_update,) * 9

        actions_text = row.get("actions", "")
        if "Assign" not in actions_text:
            return (no_update,) * 9

        # Get technician options from shared prototype user store
        tech_options = get_technician_options()
        current_technician = prototype_assignments.get_assigned_technician(row_id)

        # Show honest empty state when no technicians exist
        if not tech_options:
            empty_text = "No technicians available. Add a technician in User Administration."
            empty_style = {"display": "block", "color": "var(--color-muted)", "fontStyle": "italic", "fontSize": "var(--fs-meta)"}
        else:
            empty_text = ""
            empty_style = {"display": "none"}

        return (
            {"display": "block"},           # show drawer
            row_id,                          # store device_id
            row.get("device", "—"),          # device code
            row.get("transformer", "—"),     # transformer
            row.get("plant", "—"),           # plant
            tech_options,                    # technician dropdown options
            current_technician,              # pre-select current technician
            empty_text,                      # empty state text
            empty_style,                     # empty state visibility
        )

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
