"""Set-password callbacks (ADR-033): consume a one-time setup/reset link."""
from __future__ import annotations

import logging
from urllib.parse import parse_qs

from dash import Input, Output, State, no_update

from pages import set_password as page
from services import account_service

logger = logging.getLogger(__name__)

GENERIC_FAILURE = "The password could not be set. Please try again."
MISMATCH = "The two passwords do not match."


def token_from_search(search: str | None) -> str | None:
    """The `token` query value, or None. Exactly one value is accepted."""
    values = parse_qs((search or "").lstrip("?")).get("token", [])
    return values[0] if len(values) == 1 and values[0] else None


def submit_outputs(search, new_password, confirm):
    """(body children, message) for one submission.

    Pure of Dash so it is testable. Success replaces the whole card body; a
    fixable problem leaves the form — and the still-unconsumed link — in place.
    """
    if (new_password or "") != (confirm or ""):
        return no_update, MISMATCH
    try:
        outcome = account_service.complete_password_setup(token_from_search(search), new_password)
    except Exception:
        logger.exception("Password setup failed unexpectedly")
        return no_update, GENERIC_FAILURE
    if outcome.ok:
        return page.success_body(), ""
    if outcome.error == account_service.INVALID_LINK_MESSAGE:
        return page.invalid_link_body(), ""
    return no_update, outcome.error


def register(app) -> None:
    @app.callback(
        Output(page.BODY_ID, "children"),
        Output(page.MESSAGE_ID, "children"),
        Input(page.SUBMIT_ID, "n_clicks"),
        Input(page.CONFIRM_ID, "n_submit"),
        State("url", "search"),
        State(page.NEW_ID, "value"),
        State(page.CONFIRM_ID, "value"),
        prevent_initial_call=True,
    )
    def set_password(n_clicks, confirm_submits, search, new_password, confirm):
        if not (n_clicks or confirm_submits):
            return no_update, no_update
        return submit_outputs(search, new_password, confirm)
