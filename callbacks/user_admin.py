"""User Administration callbacks — populate table, search/filter, prototype add/edit.

All operations are frontend-only. The user list is a prototype in-memory view
model; it does not persist to any identity system. Role assignment uses
confirmed runtime roles from the client Functional Specification.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update, html

from components.user_form_drawer import (
    USER_DRAWER_ID,
    USER_HIDDEN_ID,
    USER_USERNAME_ID,
    USER_IDENTIFIER_ID,
    USER_ROLE_ID,
    USER_STATUS_ID,
    USER_CONFIRM_BTN,
    USER_CANCEL_BTN,
)

logger = logging.getLogger(__name__)

# In-memory prototype user store: username -> {username, identifier, role, status}
# Starts with the demo user from config
_mock_users: dict[str, dict] = {}

# Confirmed runtime roles from Functional Specification
CONFIRMED_ROLES = ("administrator", "technician", "general")


def _seed_mock_users() -> None:
    """Initialize mock users with the demo credential from config."""
    from config.settings import demo_auth
    if demo_auth.is_configured and demo_auth.username not in _mock_users:
        _mock_users[demo_auth.username] = {
            "username": demo_auth.username,
            "identifier": "demo@local",
            "role": "general",  # default prototype role for demo user
            "status": "active",
        }


def get_mock_users() -> list[dict]:
    """Return all mock users as a list."""
    _seed_mock_users()
    return list(_mock_users.values())


def clear_mock_users() -> None:
    """Reset mock store (for testing)."""
    _mock_users.clear()


def _validate_user_form(username: str) -> dict[str, str]:
    """Validate required fields. Returns {field: error_message} dict."""
    errors = {}
    if not username or not username.strip():
        errors["username"] = "Username is required."
    elif username.strip() in _mock_users:
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
    """Register user administration callbacks on the Dash app."""

    # Initialize mock users on first load
    _seed_mock_users()

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
            users = get_mock_users()
            rows = _build_user_rows(users, search_term or "", status_filter or "all")

            active_count = sum(1 for u in users if u.get("status") == "active")
            inactive_count = sum(1 for u in users if u.get("status") != "active")
            summary = f"{len(users)} user(s) — {active_count} active, {inactive_count} inactive"

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
            return [], [], "Error loading users.", ""

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
        ctx = dash.callback_context
        if not ctx.triggered:
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update

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
                "Add User (Prototype)",
            )

        if trigger_id == "user-admin-table" and active_cell and active_cell.get("column_id") == "actions":
            # Edit action
            row_id = active_cell.get("row_id")
            if not row_id:
                return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update

            row = next((r for r in (table_data or []) if r.get("id") == row_id), None)
            if not row:
                return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update

            # Find the full user data
            user = _mock_users.get(row_id)
            if not user:
                return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update

            return (
                {"display": "block"},
                row_id,  # existing username to edit
                "Edit User",
                user["username"],
                user.get("identifier", ""),
                user.get("role", "general"),  # existing role or default
                user.get("status", "active"),
                "Save Changes (Prototype)",
            )

        return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update

    @app.callback(
        Output(USER_DRAWER_ID, "style", allow_duplicate=True),
        Input(USER_CANCEL_BTN, "n_clicks"),
        Input("user-form-drawer-overlay", "n_clicks"),
        prevent_initial_call=True,
    )
    def close_user_drawer(cancel_clicks, overlay_clicks):
        """Close the user form drawer without making changes."""
        return {"display": "none"}

    @app.callback(
        Output("user-form-username-error", "children"),
        Output(USER_DRAWER_ID, "style", allow_duplicate=True),
        Output(USER_HIDDEN_ID, "data", allow_duplicate=True),
        Input(USER_CONFIRM_BTN, "n_clicks"),
        State(USER_HIDDEN_ID, "data"),
        State(USER_USERNAME_ID, "value"),
        State(USER_IDENTIFIER_ID, "value"),
        State(USER_ROLE_ID, "value"),
        State(USER_STATUS_ID, "value"),
        prevent_initial_call=True,
    )
    def confirm_user_form(n_clicks, existing_username, username, identifier, role, status):
        """Prototype confirm — stores in memory, no identity system write."""
        if not n_clicks:
            return no_update, no_update, no_update

        errors = _validate_user_form(username)
        if errors:
            # Show error, keep drawer open
            return errors.get("username", ""), no_update, no_update

        username = username.strip()
        identifier = identifier.strip() if identifier else ""
        role = role if role in CONFIRMED_ROLES else "general"

        if existing_username and existing_username != username:
            # Renaming: remove old, add new
            _mock_users.pop(existing_username, None)

        _mock_users[username] = {
            "username": username,
            "identifier": identifier,
            "role": role,
            "status": status or "active",
        }

        logger.info("Prototype user %s: %s (role=%s)", "updated" if existing_username else "added", username, role)

        # Close drawer
        return "", {"display": "none"}, username


# Need to import dash for callback_context
from dash import callback_context as dash