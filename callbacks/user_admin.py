"""User Administration callbacks — accounts, client-person links, lifecycle (ADR-033).

Every operation is Administrator-only and is enforced three times: the route
policy, `require_capability` here, and the actor check inside
`services.account_service`. The callbacks stay thin: gather inputs -> call the
service -> format outputs. All persistence and audit live in the service.

The one-time setup/reset link is rendered into the drawer's result slot only,
never stored client-side, and cleared whenever the drawer opens or closes.
"""
from __future__ import annotations

import logging

import dash
from dash import Input, Output, State, dcc, html, no_update

from components.status_panels import action_refused_notice, error_panel
from components.user_form_drawer import (
    USER_ACTIONS_ID,
    USER_CANCEL_BTN,
    USER_CONFIRM_BTN,
    USER_DISABLE_BTN,
    USER_DISMISS_BTN,
    USER_DRAWER_ID,
    USER_ENABLE_BTN,
    USER_FULLNAME_ID,
    USER_HIDDEN_ID,
    USER_IDENTIFIER_ID,
    USER_ISSUE_BTN,
    USER_PERSON_ID,
    USER_REFRESH_ID,
    USER_RESULT_ID,
    USER_ROLE_ID,
    USER_STATUS_ID,
    USER_USERNAME_ID,
)
from pages.user_admin import USER_TABLE_COLUMNS
from services import account_service
from services.account_service import AccountError
from services.action_guard import require_capability
from services.auth_service import current_identity
from services.authorization import AuthorizationError, MANAGE_USERS
from services.prototype_users import CONFIRMED_ROLES, get_all_users, get_user

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "active": "Active",
    "pending_activation": "Pending activation",
    "disabled": "Disabled",
}

#: Table severity ordering only (carries no visual meaning): Active first.
_SEVERITY = {"active": 0, "pending_activation": 1, "disabled": 2}

LINK_HANDOVER_NOTE = (
    "Administrative provisioning link — no email or SMS was sent. Copy it now and "
    "hand it to the user through a channel you trust. It is shown once, works once, "
    "and expires; closing this panel discards it."
)

LINK_ID = "user-issued-link"


def _validate_user_form(
    username: str, existing_username: str | None = None
) -> dict[str, str]:
    """Validate required fields. Returns {field: error_message} dict.

    `existing_username` is the record being edited: absent (an add), every
    existing name is a rival; present (an edit), the editor's own name is theirs
    to keep, and only that one — taking a DIFFERENT user's username is refused.
    """
    from services.credentials import normalize_username, username_error

    errors = {}
    name = normalize_username(username)
    if not name:
        errors["username"] = "Username is required."
    elif name != normalize_username(existing_username) and get_user(name) is not None:
        errors["username"] = "Username already exists."
    elif name != normalize_username(existing_username):
        problem = username_error(name)
        if problem:
            errors["username"] = problem
    return errors


def _format_status(status: str) -> str:
    """Human-readable status label."""
    return STATUS_LABELS.get(status, status.replace("_", " ").capitalize() if status else "—")


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


def _build_user_rows(
    users: list[dict],
    search_term: str = "",
    status_filter: str = "all",
    role_filter: str = "all",
) -> list[dict]:
    """Build table rows from user list with search/filter applied.

    `role_filter` compares the stored role ("technician"), not its label.
    """
    rows = []
    search_lower = search_term.lower().strip()

    for u in users:
        if search_lower:
            searchable = (
                f"{u['username']} {u.get('full_name', '')} {u.get('identifier', '')}"
            ).lower()
            if search_lower not in searchable:
                continue

        if status_filter != "all" and u.get("status") != status_filter:
            continue

        if role_filter != "all" and u.get("role") != role_filter:
            continue

        status = u.get("status", "active")
        person = u.get("client_person_id")
        rows.append({
            "id": u["username"],
            "username": u["username"],
            "full_name": u.get("full_name") or "—",
            "identifier": u.get("identifier") or "—",
            "role": _format_role(u.get("role", "tbd")),
            "status": _format_status(status),
            "client_person": f"Person {person}" if person is not None else "—",
            "actions": "[Edit](#)",
            "_state": status,
            "_severity": _SEVERITY.get(status, 2),
        })
    return rows


def _summary(users: list[dict]) -> str:
    """Same grammar as Device Management's summary line (ENT-6C)."""
    counts = {key: sum(1 for u in users if u.get("status") == key) for key in STATUS_LABELS}
    noun = "user" if len(users) == 1 else "users"
    return (
        f"{len(users)} {noun} total — {counts['active']} active, "
        f"{counts['pending_activation']} pending activation, {counts['disabled']} disabled"
    )


def _parse_person_id(raw) -> tuple[int | None, str | None]:
    """(client_person_id, error). Blank means "no link"."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, "Client person ID must be a whole number."
    if value < 1:
        return None, "Client person ID must be a positive number."
    return value, None


def _error_note(message: str) -> html.Div:
    return html.Div(message, className="user-form-drawer__error", role="alert")


def _status_note(message: str) -> html.Div:
    return html.Div(message, className="user-form-drawer__hint", role="status")


def _link_panel(link: account_service.IssuedLink) -> html.Div:
    kind = "Setup link" if link.purpose == account_service.PURPOSE_SETUP else "Password reset link"
    return html.Div(
        className="user-form-drawer__link",
        role="status",
        children=[
            html.Strong(f"{kind} for {link.username}"),
            html.P(LINK_HANDOVER_NOTE),
            html.Code(link.url, id=LINK_ID, className="user-form-drawer__link-url"),
            dcc.Clipboard(target_id=LINK_ID, title="Copy link", className="user-form-drawer__copy"),
            html.P(f"Expires {link.expires_at:%Y-%m-%d %H:%M} UTC. Single use."),
        ],
    )


def _admin_or_none():
    """The current Administrator identity, or None (after a logged refusal)."""
    user = current_identity()
    try:
        require_capability(user, MANAGE_USERS)
    except AuthorizationError:
        logger.warning(
            "User administration action refused: %r is not an administrator.",
            user.username if user else None,
        )
        return None
    return user


def _target_user_id(admin, username: str | None) -> int | None:
    """The stable user_id behind a table row's username, via the audited
    Administrator-only listing."""
    for stored in account_service.list_accounts(actor_user_id=admin.user_id):
        if stored.username == (username or "").strip().lower():
            return stored.user_id
    return None


def _lifecycle_view(status: str | None, has_password: bool = False):
    """(actions style, issue label, disable style, enable style) for a status."""
    shown, hidden = {"display": "block"}, {"display": "none"}
    if status is None:
        return hidden, no_update, hidden, hidden
    if status == "disabled":
        return shown, "Issue setup link", hidden, {"display": "inline-block"}
    label = "Issue setup link" if status == "pending_activation" else "Issue password reset link"
    return shown, label, {"display": "inline-block"}, hidden


def register(app) -> None:
    """Register user administration callbacks on the Dash app."""

    @app.callback(
        Output("user-admin-table", "data"),
        Output("user-admin-table", "columns"),
        Output("user-admin-error", "children"),
        Output("user-admin-summary", "children"),
        Input("page-context", "data"),
        Input("user-admin-search", "value"),
        Input("user-admin-status-filter", "value"),
        Input("user-admin-role-filter", "value"),
        Input(USER_REFRESH_ID, "data"),
        prevent_initial_call=True,
    )
    def populate_user_admin(context, search_term, status_filter, role_filter="all", _refresh=None):
        if not context or context.get("route") != "admin_users":
            return (no_update,) * 4

        # P0-4 (AUTH-HARDEN-1). `admin_users` is administrator-only by
        # ROUTE_POLICY, but this callback is independently invokable with a
        # forged page-context and must not trust it.
        try:
            require_capability(current_identity(), MANAGE_USERS)
        except AuthorizationError:
            logger.warning("User administration data refused: not an administrator.")
            return [], [], error_panel(), ""

        try:
            users = get_all_users()
            rows = _build_user_rows(
                users, search_term or "", status_filter or "all", role_filter or "all"
            )
            return rows, USER_TABLE_COLUMNS, None, _summary(users)
        except Exception:
            logger.exception("Failed to load user administration data")
            return [], [], error_panel(), ""

    @app.callback(
        Output(USER_DRAWER_ID, "style"),
        Output(USER_HIDDEN_ID, "data"),
        Output("user-form-drawer-title", "children"),
        Output(USER_USERNAME_ID, "value"),
        Output(USER_FULLNAME_ID, "value"),
        Output(USER_IDENTIFIER_ID, "value"),
        Output(USER_ROLE_ID, "value"),
        Output(USER_PERSON_ID, "value"),
        Output(USER_STATUS_ID, "children"),
        Output(USER_CONFIRM_BTN, "children"),
        Output(USER_ACTIONS_ID, "style"),
        Output(USER_ISSUE_BTN, "children"),
        Output(USER_DISABLE_BTN, "style"),
        Output(USER_ENABLE_BTN, "style"),
        Output(USER_RESULT_ID, "children"),
        Output("user-form-username-error", "children", allow_duplicate=True),
        Input("user-admin-add-btn", "n_clicks"),
        Input("user-admin-table", "active_cell"),
        State("user-admin-table", "data"),
        prevent_initial_call=True,
    )
    def open_user_drawer(add_clicks, active_cell, table_data):
        """Open drawer for Add User or Edit action.

        Loads an existing user's editable data for the Edit path, so it needs
        the same Administrator guard as `populate_user_admin` — a table row
        alone does not prove the caller is entitled to open it.
        """
        nothing = (no_update,) * 16
        if _admin_or_none() is None:
            return nothing

        ctx = dash.callback_context
        if not ctx.triggered:
            return nothing
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if trigger_id == "user-admin-add-btn":
            actions, issue, disable, enable = _lifecycle_view(None)
            return (
                {"display": "block"}, None, "Add User", "", "", "", "general", None,
                "Pending activation (set when the account is created)", "Create account",
                actions, issue, disable, enable, "", "",
            )

        if trigger_id == "user-admin-table" and active_cell and active_cell.get("column_id") == "actions":
            row_id = active_cell.get("row_id")
            if not row_id:
                return nothing
            row = next((r for r in (table_data or []) if r.get("id") == row_id), None)
            if not row:
                return nothing
            user = get_user(row_id)
            if not user:
                return nothing
            actions, issue, disable, enable = _lifecycle_view(
                user.get("status"), user.get("has_password", False)
            )
            return (
                {"display": "block"}, row_id, "Edit User", user["username"],
                user.get("full_name", ""), user.get("identifier", ""),
                user.get("role", "general"), user.get("client_person_id"),
                _format_status(user.get("status", "")), "Save Changes",
                actions, issue, disable, enable, "", "",
            )

        return nothing

    @app.callback(
        Output(USER_DRAWER_ID, "style", allow_duplicate=True),
        Output(USER_RESULT_ID, "children", allow_duplicate=True),
        # A DataTable does not report a click on the cell that is already
        # active, so the drawer could not be reopened for the same row.
        Output("user-admin-table", "active_cell", allow_duplicate=True),
        Input(USER_CANCEL_BTN, "n_clicks"),
        Input(USER_DISMISS_BTN, "n_clicks"),
        Input("user-form-drawer-overlay", "n_clicks"),
        prevent_initial_call=True,
    )
    def close_user_drawer(cancel_clicks, dismiss_clicks, overlay_clicks):
        """Close the drawer, discarding any one-time link it was showing."""
        return {"display": "none"}, "", None

    @app.callback(
        Output("user-form-username-error", "children"),
        Output(USER_RESULT_ID, "children", allow_duplicate=True),
        Output(USER_DRAWER_ID, "style", allow_duplicate=True),
        Output(USER_HIDDEN_ID, "data", allow_duplicate=True),
        Output(USER_REFRESH_ID, "data"),
        Output("user-admin-table", "active_cell", allow_duplicate=True),
        Input(USER_CONFIRM_BTN, "n_clicks"),
        State(USER_HIDDEN_ID, "data"),
        State(USER_USERNAME_ID, "value"),
        State(USER_FULLNAME_ID, "value"),
        State(USER_IDENTIFIER_ID, "value"),
        State(USER_ROLE_ID, "value"),
        State(USER_PERSON_ID, "value"),
        State(USER_REFRESH_ID, "data"),
        prevent_initial_call=True,
    )
    def confirm_user_form(
        n_clicks, existing_username, username, full_name, identifier, role, person_id, refresh
    ):
        """Create or update an account with an audited, actor-attributed write.

        The strict-actor rule (AUD-1): without an Administrator identity there
        is no one to attribute the change to, so nothing is written. The result
        slot carries every refusal so a failed save is never silent.
        """
        if not n_clicks:
            return (no_update,) * 6

        user = current_identity()
        try:
            require_capability(user, MANAGE_USERS)
        except AuthorizationError:
            logger.warning(
                "User save refused: %r is not an administrator.",
                user.username if user else None,
            )
            return no_update, action_refused_notice(), no_update, no_update, no_update, no_update

        errors = _validate_user_form(username, existing_username)
        if errors:
            return errors.get("username", ""), "", no_update, no_update, no_update, no_update

        link_id, link_error = _parse_person_id(person_id)
        if link_error:
            return "", _error_note(link_error), no_update, no_update, no_update, no_update

        role = role if role in CONFIRMED_ROLES else "general"
        try:
            if existing_username:
                target_id = _target_user_id(user, existing_username)
                if target_id is None:
                    return "", _error_note("No such account."), no_update, no_update, no_update, no_update
                account_service.update_account(
                    actor_user_id=user.user_id, user_id=target_id, username=username,
                    full_name=full_name, email_address=identifier, role=role,
                    client_person_id=link_id,
                )
            else:
                account_service.create_account(
                    actor_user_id=user.user_id, username=username, full_name=full_name,
                    email_address=identifier, role=role, client_person_id=link_id,
                )
        except AccountError as exc:
            return "", _error_note(str(exc)), no_update, no_update, no_update, no_update
        except Exception:
            logger.exception("Account save failed")
            return "", _error_note("The account could not be saved."), no_update, no_update, no_update, no_update

        logger.info("Account %s by user_id=%s", "updated" if existing_username else "created", user.user_id)
        return "", "", {"display": "none"}, None, (refresh or 0) + 1, None

    @app.callback(
        Output(USER_RESULT_ID, "children", allow_duplicate=True),
        Output(USER_STATUS_ID, "children", allow_duplicate=True),
        Output(USER_ISSUE_BTN, "children", allow_duplicate=True),
        Output(USER_DISABLE_BTN, "style", allow_duplicate=True),
        Output(USER_ENABLE_BTN, "style", allow_duplicate=True),
        Output(USER_REFRESH_ID, "data", allow_duplicate=True),
        Input(USER_ISSUE_BTN, "n_clicks"),
        Input(USER_DISABLE_BTN, "n_clicks"),
        Input(USER_ENABLE_BTN, "n_clicks"),
        State(USER_HIDDEN_ID, "data"),
        State(USER_REFRESH_ID, "data"),
        prevent_initial_call=True,
    )
    def account_lifecycle(issue_clicks, disable_clicks, enable_clicks, username, refresh):
        """Issue a setup/reset link, disable, or re-enable the open account."""
        nothing = (no_update,) * 6
        ctx = dash.callback_context
        if not ctx.triggered or not username:
            return nothing
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        # A button re-mounted by a drawer refresh reports n_clicks=0: not a click.
        if not any((issue_clicks, disable_clicks, enable_clicks)):
            return nothing

        admin = _admin_or_none()
        if admin is None:
            return action_refused_notice(), no_update, no_update, no_update, no_update, no_update

        try:
            target_id = _target_user_id(admin, username)
            if target_id is None:
                return _error_note("No such account."), *nothing[1:]
            link_panel = ""
            if trigger_id == USER_ISSUE_BTN:
                link_panel = _link_panel(
                    account_service.issue_link(actor_user_id=admin.user_id, user_id=target_id)
                )
            elif trigger_id == USER_DISABLE_BTN:
                account_service.disable_account(actor_user_id=admin.user_id, user_id=target_id)
                link_panel = _status_note("Account disabled. Existing sessions are ended; assignments are untouched.")
            elif trigger_id == USER_ENABLE_BTN:
                account_service.enable_account(actor_user_id=admin.user_id, user_id=target_id)
                link_panel = _status_note("Account re-enabled.")
            else:
                return nothing
            fresh = get_user(username) or {}
        except AccountError as exc:
            return _error_note(str(exc)), *nothing[1:]
        except Exception:
            logger.exception("Account action failed")
            return _error_note("The action could not be completed."), *nothing[1:]

        _, issue, disable, enable = _lifecycle_view(fresh.get("status"))
        return (
            link_panel, _format_status(fresh.get("status", "")), issue, disable, enable,
            (refresh or 0) + 1,
        )
