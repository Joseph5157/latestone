"""User Administration callbacks — populate table, search/filter, prototype add/edit.

All operations are frontend-only. The user list is a prototype in-memory view
model; it does not persist to any identity system. User state is shared via
services/prototype_users.py so device workflows can access technician data.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update, html

from components.status_panels import action_refused_notice, error_panel
from components.user_form_drawer import (
    USER_DRAWER_ID,
    USER_HIDDEN_ID,
    USER_RESULT_ID,
    USER_USERNAME_ID,
    USER_IDENTIFIER_ID,
    USER_ROLE_ID,
    USER_STATUS_ID,
    USER_CONFIRM_BTN,
    USER_CANCEL_BTN,
    USER_DISMISS_BTN,
)
from services.auth_service import from_session
from services.prototype_users import (
    get_all_users,
    get_user,
    upsert_user,
    clear_all_users,
    CONFIRMED_ROLES,
)

logger = logging.getLogger(__name__)


def _validate_user_form(
    username: str, existing_username: str | None = None
) -> dict[str, str]:
    """Validate required fields. Returns {field: error_message} dict.

    `existing_username` is the record being edited, and without it this
    function cannot tell "someone else already has this name" from "this user
    still has their own name". It previously had no way to know, so re-saving
    a user under their unchanged username was refused as a duplicate.

    Absent (an add), every existing name is a rival. Present (an edit), the
    editor's own name is theirs to keep — and only that one name; taking a
    DIFFERENT user's username is still refused.
    """
    errors = {}
    name = (username or "").strip()
    if not name:
        errors["username"] = "Username is required."
    elif name != (existing_username or "") and get_user(name) is not None:
        errors["username"] = "Username already exists."
    return errors


def _format_status(status: str) -> str:
    """Human-readable status label."""
    return status.capitalize() if status else "—"


def _format_role(role: str) -> str:
    """Human-readable role label for table display."""
    if role == "administrator":
        return "Administrator"
    if role == "technician":
        return "Technician"
    if role == "general":
        return "General User"
    if role == "tbd":
        return "Unassigned"  # legacy mock users without explicit role
    return role.capitalize()


def _build_user_rows(users: list[dict], search_term: str = "", status_filter: str = "all") -> list[dict]:
    """Build table rows from user list with search/filter applied."""
    rows = []
    search_lower = search_term.lower().strip()

    for u in users:
        # Apply search filter
        if search_lower:
            searchable = f"{u['username']} {u.get('identifier', '')}".lower()
            if search_lower not in searchable:
                continue

        # Apply status filter
        if status_filter != "all" and u.get("status") != status_filter:
            continue

        role_label = _format_role(u.get("role", "tbd"))
        actions = "[Edit](#)"

        rows.append({
            "id": u["username"],
            "username": u["username"],
            "identifier": u.get("identifier", "—"),
            "role": role_label,
            "status": _format_status(u.get("status", "active")),
            "actions": actions,
            "_state": u.get("status", "active"),
            "_severity": 0 if u.get("status") == "active" else 2,
        })
    return rows


def register(app) -> None:
    """Register user administration callbacks on the Dash app.

    Registration wires callbacks and nothing else. It used to call
    `seed_demo_user()` here — a leftover from the in-memory prototype store,
    where seeding was free. Against PostgreSQL it made importing `app` open a
    connection, so the app could not be imported (or its pure-logic tests
    collected) without a running database, and a module import performed a
    write. Nothing is lost by dropping it: every path that reads users seeds
    first — `auth_service.authenticate()` before its lookup, and
    `prototype_users.get_all_users()` / `.get_user()` on entry.
    """

    @app.callback(
        Output("user-admin-table", "data"),
        Output("user-admin-table", "columns"),
        Output("user-admin-error", "children"),
        Output("user-admin-summary", "children"),
        Input("page-context", "data"),
        Input("user-admin-search", "value"),
        Input("user-admin-status-filter", "value"),
        prevent_initial_call=True,
    )
    def populate_user_admin(context, search_term, status_filter):
        if not context or context.get("route") != "admin_users":
            return (no_update,) * 4

        try:
            users = get_all_users()
            rows = _build_user_rows(users, search_term or "", status_filter or "all")

            active_count = sum(1 for u in users if u.get("status") == "active")
            inactive_count = sum(1 for u in users if u.get("status") != "active")
            # Same grammar as Device Management's summary line (ENT-6C):
            # "N <noun> total — N active, N inactive", pluralised without
            # the awkward "(s)" form.
            noun = "user" if len(users) == 1 else "users"
            summary = f"{len(users)} {noun} total — {active_count} active, {inactive_count} inactive"

            columns = [
                {"name": "User", "id": "username"},
                {"name": "Identifier", "id": "identifier"},
                {"name": "Role", "id": "role"},
                {"name": "Status", "id": "status"},
                {"name": "Actions", "id": "actions", "presentation": "markdown"},
            ]

            return rows, columns, None, summary

        except Exception:
            logger.exception("Failed to load user administration data")
            return [], [], error_panel(), ""

    @app.callback(
        Output(USER_DRAWER_ID, "style"),
        Output(USER_HIDDEN_ID, "data"),
        Output("user-form-drawer-title", "children"),
        Output(USER_USERNAME_ID, "value"),
        Output(USER_IDENTIFIER_ID, "value"),
        Output(USER_ROLE_ID, "value"),
        Output(USER_STATUS_ID, "value"),
        Output(USER_CONFIRM_BTN, "children"),
        Input("user-admin-add-btn", "n_clicks"),
        Input("user-admin-table", "active_cell"),
        State("user-admin-table", "data"),
        prevent_initial_call=True,
    )
    def open_user_drawer(add_clicks, active_cell, table_data):
        """Open drawer for Add User or Edit action."""
        ctx = __import__("dash").callback_context
        if not ctx.triggered:
            return (no_update,) * 8

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if trigger_id == "user-admin-add-btn":
            # Add User
            return (
                {"display": "block"},
                None,  # no existing username
                "Add User",
                "",  # empty username
                "",  # empty identifier
                "general",  # default role
                "active",  # default status
                "Add User",
            )

        if trigger_id == "user-admin-table" and active_cell and active_cell.get("column_id") == "actions":
            # Edit action
            row_id = active_cell.get("row_id")
            if not row_id:
                return (no_update,) * 8

            row = next((r for r in (table_data or []) if r.get("id") == row_id), None)
            if not row:
                return (no_update,) * 8

            # Find the full user data from shared store
            user = get_user(row_id)
            if not user:
                return (no_update,) * 8

            return (
                {"display": "block"},
                row_id,  # existing username to edit
                "Edit User",
                user["username"],
                user.get("identifier", ""),
                user.get("role", "general"),  # existing role or default
                user.get("status", "active"),
                "Save Changes",
            )

        return (no_update,) * 8

    @app.callback(
        Output(USER_DRAWER_ID, "style", allow_duplicate=True),
        Input(USER_CANCEL_BTN, "n_clicks"),
        Input(USER_DISMISS_BTN, "n_clicks"),
        Input("user-form-drawer-overlay", "n_clicks"),
        prevent_initial_call=True,
    )
    def close_user_drawer(cancel_clicks, dismiss_clicks, overlay_clicks):
        """Close the user form drawer without making changes."""
        return {"display": "none"}

    @app.callback(
        Output("user-form-username-error", "children"),
        Output(USER_RESULT_ID, "children"),
        Output(USER_DRAWER_ID, "style", allow_duplicate=True),
        Output(USER_HIDDEN_ID, "data", allow_duplicate=True),
        Input(USER_CONFIRM_BTN, "n_clicks"),
        State(USER_HIDDEN_ID, "data"),
        State(USER_USERNAME_ID, "value"),
        State(USER_IDENTIFIER_ID, "value"),
        State(USER_ROLE_ID, "value"),
        State(USER_STATUS_ID, "value"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def confirm_user_form(n_clicks, existing_username, username, identifier, role, status, auth_data):
        """Persist the user form (DB-2) with an audited, actor-attributed write.

        AUD-1 strict-actor rule: without a valid authenticated session there
        is no one to attribute the change to, so the operation fails closed
        and nothing is written (the drawer stays open). ENT-5: that refusal
        is rendered in the drawer's result slot rather than being silent.
        """
        if not n_clicks:
            return no_update, no_update, no_update, no_update

        # BIND the identity, don't just test it. The result was previously
        # discarded and `user.user_id` read further down from a name that was
        # never bound, so every save raised NameError. The actor is the whole
        # point of the AUD-1 rule below: an audited write needs the identity,
        # not merely the knowledge that one exists.
        user = from_session(auth_data)
        if user is None:
            logger.warning("User save refused: no valid session.")
            return no_update, action_refused_notice(), no_update, no_update

        errors = _validate_user_form(username, existing_username)
        if errors:
            # Show error, keep drawer open
            return errors.get("username", ""), "", no_update, no_update

        username = username.strip()
        identifier = identifier.strip() if identifier else ""
        role = role if role in CONFIRMED_ROLES else "general"

        if existing_username and existing_username != username:
            # Renaming: remove old, add new
            from services.prototype_users import remove_user
            remove_user(existing_username)

        upsert_user(
            username, identifier, role, status or "active",
            actor_user_id=user.user_id,
        )

        logger.info("Audited user %s: %s (role=%s)", "updated" if existing_username else "added", username, role)

        # Close drawer
        return "", "", {"display": "none"}, username
