"""Device Assignment callbacks — open drawer, technician selection, persisted submit.

Technician assignment is persisted (DB-3) via
services/prototype_assignments.py, backed by
plant_monitoring.user_device_assignments. Technician *options* come from
the shared prototype user store, services/prototype_users.py.

There is no asset (device -> transformer) assignment here: moving a device
between transformers is the registration/hierarchy workflow, and the drawer
does not offer a control that would imply otherwise (ENT-5 D1/D2).

Outcome grammar (ENT-5): every confirm renders exactly one result into the
drawer's result slot — success, failure or the shared refusal notice — and
the drawer stays open so the operator never loses context. Authorization is
checked before any write; a refusal writes nothing.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update, html

from components.assign_device_drawer import (
    ASSIGN_DRAWER_ID,
    ASSIGN_DEVICE_ID,
    ASSIGN_RESULT_ID,
    ASSIGN_TECHNICIAN_ID,
    ASSIGN_CONFIRM_BTN,
    ASSIGN_CANCEL_BTN,
    ASSIGN_CLOSE_BTN,
)
from components.status_panels import action_refused_notice
from routes import parse_assign_request
from services import prototype_assignments
from services.action_guard import require_action, require_capability
from services.auth_service import current_identity
from services.authorization import AuthorizationError, MANAGE_ASSIGNMENT, MANAGE_DEVICES
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

    Returns None when there is no row to open on, which each caller turns
    into `no_update`. It also used to return None for "a row whose actions do
    not include Assign" — a check on the shared Actions cell's markdown that
    never fired, because every row carried the same literal string. Which
    action was clicked is now answered by `column_id`, upstream of here, and
    whether the device is addressable at all is answered by `find_device_row`
    against the rendered table. Callers append the result-slot clear
    themselves, so this helper stays purely about opening.
    """
    if not row:
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


def _open_outputs(state: dict | None):
    """The open callbacks' full output tuple: the nine open values, a
    cleared result slot and the default secondary-button label, so feedback
    from a previous visit can never bleed into a freshly opened drawer."""
    if state is None:
        return (no_update,) * 11
    return (*state, "", "Cancel")


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
        Output(ASSIGN_RESULT_ID, "children"),
        Output(ASSIGN_CLOSE_BTN, "children"),
        Input("device-admin-table", "active_cell"),
        State("device-admin-table", "data"),
        prevent_initial_call=True,
    )
    def open_assign_drawer(active_cell, table_data):
        """Open the assignment drawer when the Assign column is clicked.

        Keyed on the `assign` column, which exists precisely so this and
        `open_manage_drawer` stop receiving the same click.

        AUTH-HARDEN-1 (Phase 1F): this reads `get_technician_options()` and
        `get_assigned_technician(device_id)` for whatever device_id the
        caller supplies — normally a row from the already-admin-gated table,
        but this callback is independently invokable with a fabricated
        `table_data`/`active_cell`, and assignment is administrator-only
        content. Refused before either read runs.
        """
        try:
            require_capability(current_identity(), MANAGE_DEVICES)
        except AuthorizationError:
            return (no_update,) * 11

        if not active_cell or active_cell.get("column_id") != "assign":
            return (no_update,) * 11

        row = find_device_row(table_data, active_cell.get("row_id"))
        return _open_outputs(assign_drawer_open_state(row))

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

        Same guard as `open_assign_drawer` above, and for the same reason.
        """
        try:
            require_capability(current_identity(), MANAGE_DEVICES)
        except AuthorizationError:
            return (no_update,) * 11

        row = find_device_row(table_data, parse_assign_request(search))
        return _open_outputs(assign_drawer_open_state(row))

    @app.callback(
        Output(ASSIGN_DRAWER_ID, "style", allow_duplicate=True),
        Input(ASSIGN_CANCEL_BTN, "n_clicks"),
        Input(ASSIGN_CLOSE_BTN, "n_clicks"),
        Input("assign-drawer-overlay", "n_clicks"),
        prevent_initial_call=True,
    )
    def close_assign_drawer(cancel_clicks, close_clicks, overlay_clicks):
        """Close the assignment drawer (×, Cancel/Close button or overlay)."""
        return {"display": "none"}

    @app.callback(
        Output(ASSIGN_RESULT_ID, "children", allow_duplicate=True),
        Output(ASSIGN_CLOSE_BTN, "children", allow_duplicate=True),
        Input(ASSIGN_CONFIRM_BTN, "n_clicks"),
        State(ASSIGN_DEVICE_ID, "data"),
        State(ASSIGN_TECHNICIAN_ID, "value"),
        State("auth-store", "data"),
        # MOBBIN-UX-3: transient persistence state only — Dash applies the
        # "during" values the instant the request fires and restores the
        # "after" values once this callback returns OR raises, with no
        # change to what it returns. This is also what prevents a repeat
        # click from starting a second write while one is in flight: the
        # button is disabled for the whole round trip, not just after this
        # function decides an outcome.
        running=[
            (Output(ASSIGN_CONFIRM_BTN, "disabled"), True, False),
            (Output(ASSIGN_CONFIRM_BTN, "children"), "Saving…", "Confirm Assignment"),
        ],
        prevent_initial_call=True,
    )
    def confirm_assignment(n_clicks, device_id, technician, auth_data):
        """Persist the technician assignment (DB-3) and render one outcome.

        Managing an assignment is administrator-only, including for a
        technician who currently holds this device: the assignment is what
        grants their authority, so being able to edit it would let them
        widen their own scope. The rule lives in the policy table; this
        callback only supplies identity, action and target.

        The drawer stays open whatever the outcome: success names what was
        saved and relabels the secondary action to "Close", failure says
        nothing was saved, refusal renders the shared notice with zero
        writes. This function's own return values are unchanged by the
        `running` state above — no optimistic table/assignment state is
        rendered until one of these outcomes actually returns.
        """
        if not n_clicks or not device_id:
            return no_update, no_update

        try:
            user = current_identity()
            require_action(user, MANAGE_ASSIGNMENT, device_id=device_id)
        except AuthorizationError:
            return action_refused_notice(), no_update

        try:
            if technician:
                prototype_assignments.assign_technician(
                    device_id, technician, actor_user_id=user.user_id
                )
                detail = (
                    f"{technician} is assigned to this RTL and recorded as "
                    "responsible for it."
                )
                logger.info(
                    "Technician assignment: device %s -> technician %s",
                    device_id, technician,
                )
            elif prototype_assignments.get_assigned_technician(device_id) is not None:
                prototype_assignments.unassign_technician(
                    device_id, actor_user_id=user.user_id
                )
                detail = "No technician is assigned to this RTL."
                logger.info("Technician assignment cleared: device %s", device_id)
            else:
                # Nothing selected and nothing stored: state the outcome
                # rather than claiming a save happened.
                return (
                    html.Div(
                        className="status-panel status-panel--inactive",
                        children=[
                            html.Strong("Nothing to save. "),
                            html.Span(
                                "No technician is assigned to this RTL, so no "
                                "change was made."
                            ),
                        ],
                    ),
                    no_update,
                )
        except ValueError:
            logger.exception(
                "Failed to assign technician %s to device %s",
                technician, device_id,
            )
            return (
                html.Div(
                    className="status-panel status-panel--inactive",
                    children=[
                        html.Strong("Not saved. "),
                        html.Span(
                            "The technician assignment could not be stored. "
                            "Nothing was changed. Please try again."
                        ),
                    ],
                ),
                "Cancel",
            )

        return (
            html.Div(
                className="status-panel status-panel--success",
                children=[
                    html.Strong("Assignment saved. "),
                    html.Span(detail),
                ],
            ),
            "Close",
        )
