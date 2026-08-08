"""Authentication callbacks — isolated so they can later be replaced."""
from __future__ import annotations

from dash import Input, Output, State, callback, no_update

from config.settings import demo_auth


def register(app) -> None:
    """Register auth callbacks on the Dash app."""

    @app.callback(
        Output("url", "pathname"),
        Input("login-button", "n_clicks"),
        State("username-input", "value"),
        State("password-input", "value"),
        prevent_initial_call=True,
    )
    def handle_login(n_clicks, username, password):
        if n_clicks is None:
            return no_update
        if username == demo_auth.username and password == demo_auth.password:
            return "/plants"
        return no_update

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("logout-button", "n_clicks"),
        prevent_initial_call=True,
    )
    def handle_logout(n_clicks):
        if n_clicks is None:
            return no_update
        return "/login"
