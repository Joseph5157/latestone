"""Login page layout."""
from __future__ import annotations

from dash import dcc, html


def login_layout():
    return html.Div(
        className="login-page",
        children=[
            html.Div(
                className="login-card",
                children=[
                    html.H1("Power Plant Monitoring System", className="login-title"),
                    html.P("Sign in to continue", className="login-subtitle"),
                    dcc.Input(
                        id="login-username",
                        type="text",
                        placeholder="Username",
                        className="login-input",
                        n_submit=0,
                    ),
                    html.Div(
                        className="login-password-row",
                        children=[
                            dcc.Input(
                                id="login-password",
                                type="password",
                                placeholder="Password",
                                className="login-input",
                                n_submit=0,
                            ),
                            html.Button(
                                "Show",
                                id="toggle-password-btn",
                                className="toggle-password-btn",
                                n_clicks=0,
                            ),
                        ],
                    ),
                    html.Button("Log In", id="login-button", className="login-button", n_clicks=0),
                    html.Div(id="login-error", className="login-error"),
                ],
            )
        ],
    )
