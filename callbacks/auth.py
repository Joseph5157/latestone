"""Authentication callbacks — isolated so they can later be replaced."""
from __future__ import annotations

from dash import Input, Output, State, no_update

from services import auth_service


def register(app) -> None:
    """Register auth callbacks on the Dash app."""

    @app.callback(
        Output("login-error", "children"),
        Output("auth-store", "data"),
        Input("login-button", "n_clicks"),
        State("login-username", "value"),
        State("login-password", "value"),
        prevent_initial_call=True,
    )
    def handle_login(n_clicks, username, password):
        # Deliberately does not redirect: leaving `url.pathname`/`search` untouched
        # means a successful login re-triggers routing (auth-store is a routing
        # Input) on whatever URL the user actually requested, including deep links.
        # `not n_clicks`, not `is None`: the router inserts the login form
        # dynamically, so this fires on insertion with the layout's n_clicks=0.
        # `prevent_initial_call` only suppresses the app's very first load, so an
        # `is None` guard let that through and greeted every visitor with
        # "Invalid username or password." before they had typed anything.
        if not n_clicks:
            return no_update, no_update
        # Credential checking stays behind auth_service so swapping in the
        # client's real authentication needs no change to callback code.
        if auth_service.verify_credentials(username, password):
            return "", {"authenticated": True}
        return "Invalid username or password.", no_update

    @app.callback(
        Output("login-password", "type"),
        Output("toggle-password-btn", "children"),
        Input("toggle-password-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_password_visibility(n_clicks):
        showing = bool(n_clicks) and n_clicks % 2 == 1
        return ("text", "Hide") if showing else ("password", "Show")

    # Logout is a plain `<a href="/logout">` (see components.app_header) rather
    # than a callback: a full page load resets the memory-backed auth-store,
    # which is simpler than a round trip through the server for a client-only
    # sign-out.
