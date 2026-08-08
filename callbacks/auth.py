"""Authentication callbacks — isolated so they can later be replaced."""
from __future__ import annotations

from dash import Input, Output, State, callback, no_update

from config.settings import demo_auth


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
        if n_clicks is None:
            return no_update, no_update
        if username == demo_auth.username and password == demo_auth.password:
            return "", {"authenticated": True}
        return "Invalid username or password.", no_update

    # Logout is a plain `<a href="/logout">` (see components.app_header) rather
    # than a callback: a full page load resets the memory-backed auth-store,
    # which is simpler than a round trip through the server for a client-only
    # sign-out.
