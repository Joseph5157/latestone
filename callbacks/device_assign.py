"""Device Assignment callbacks — open drawer, cascade, mock submit.

All assignment actions are frontend-only. The mock adapter stores the
latest assignment in a dcc.Store; it does not write to any database.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update, html

from components.assign_device_drawer import (
    ASSIGN_DRAWER_ID,
    ASSIGN_DEVICE_ID,
    ASSIGN_PLANT_ID,
    ASSIGN_TRANSFORMER_ID,
    ASSIGN_CONFIRM_BTN,
    ASSIGN_CANCEL_BTN,
)
from services import hierarchy_service

logger = logging.getLogger(__name__)

# In-memory store for prototype assignments: device_id -> transformer_id
_mock_assignments: dict[str, str] = {}


def get_mock_assignment(device_id: str) -> str | None:
    """Read the mock assignment for a device (for testing)."""
    return _mock_assignments.get(device_id)


def clear_mock_assignments() -> None:
    """Reset the mock store (for testing)."""
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
        Input("device-admin-table", "active_cell"),
        State("device-admin-table", "data"),
        prevent_initial_call=True,
    )
    def open_assign_drawer(active_cell, table_data):
        """Open the assignment drawer when Assign is clicked."""
        if not active_cell or active_cell.get("column_id") != "actions":
            return no_update, no_update, no_update, no_update, no_update

        row_id = active_cell.get("row_id")
        if not row_id:
            return no_update, no_update, no_update, no_update, no_update

        # Find the row data
        row = next((r for r in (table_data or []) if r.get("id") == row_id), None)
        if not row:
            return no_update, no_update, no_update, no_update, no_update

        return (
            {"display": "block"},  # show drawer
            row_id,                # store device_id
            row.get("device", "—"),
            row.get("transformer", "—"),
            row.get("plant", "—"),
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
        prevent_initial_call=True,
    )
    def confirm_assignment(n_clicks, device_id, plant_id, transformer_id):
        """Prototype confirm — stores in memory, no database write."""
        if not n_clicks or not device_id or not transformer_id:
            return no_update, no_update

        # Mock assignment: store the mapping
        _mock_assignments[device_id] = transformer_id

        logger.info(
            "Prototype assignment: device %s -> transformer %s",
            device_id, transformer_id,
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
