"""Login page layout — split composition, form left / hero right.

Visual refinement only. Every `id` below is a callback contract in
`callbacks/auth.py` and must not be renamed:

    login-username  n_submit (Input), value (State)
    login-password  n_submit (Input), value (State), type (Output)
    toggle-password-btn  n_clicks (Input), children (Output)
    login-button    n_clicks (Input)
    login-error     children (Output)

`n_submit=0` on both inputs is load-bearing, not decoration. The router inserts
this form dynamically, so the auth callback fires on insertion;
`login_was_submitted` reads all-zero counters as "nobody asked to log in yet".
Dropping the explicit zeros sends `None` instead and re-opens NEW-14, where
every visitor was greeted with "Invalid username or password." before typing.

The password toggle's label is server-rendered ("Show"/"Hide" come from the
callback), so it must stay a text button rather than becoming a CSS-only icon.
"""
from __future__ import annotations

from dash import dcc, html

HERO_HEADLINE = "Operational visibility across the fleet"
HERO_SUPPORT = "Monitor plants, transformers and devices from one workspace."

HERO_ASSET = "login-industrial-hero.png"


def _field(label: str, field_id: str, control) -> html.Div:
    """A labelled control. `htmlFor` is what makes the label clickable and
    announced — the previous form carried placeholders only, which screen
    readers may drop and which vanish the moment the operator types."""
    return html.Div(
        className="login-field",
        children=[
            html.Label(label, htmlFor=field_id, className="login-label"),
            control,
        ],
    )


def login_layout():
    return html.Div(
        className="login-page",
        children=[
            html.Div(
                className="login-shell",
                children=[
                    html.Div(
                        className="login-form-panel",
                        children=[
                            html.Div(
                                className="login-form",
                                children=[
                                    html.P(
                                        "Power Plant Monitoring",
                                        className="login-eyebrow",
                                    ),
                                    html.H1("Welcome back", className="login-heading"),
                                    html.P(
                                        "Sign in to access the monitoring workspace.",
                                        className="login-support",
                                    ),
                                    _field(
                                        "Username",
                                        "login-username",
                                        dcc.Input(
                                            id="login-username",
                                            type="text",
                                            className="login-input",
                                            autoComplete="username",
                                            n_submit=0,
                                        ),
                                    ),
                                    _field(
                                        "Password",
                                        "login-password",
                                        html.Div(
                                            className="login-password-row",
                                            children=[
                                                dcc.Input(
                                                    id="login-password",
                                                    type="password",
                                                    className="login-input",
                                                    autoComplete="current-password",
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
                                    ),
                                    html.Button(
                                        "Sign in",
                                        id="login-button",
                                        className="login-button",
                                        n_clicks=0,
                                    ),
                                    # role="alert" so the failure is announced rather
                                    # than only rendered. The message is a sentence,
                                    # so the state never depends on colour; the CSS
                                    # marker is additive.
                                    html.Div(
                                        id="login-error",
                                        className="login-error",
                                        role="alert",
                                    ),
                                ],
                            )
                        ],
                    ),
                    # Decorative: the illustration is a CSS background so it needs
                    # no alt text, and the only content here is the overlay copy.
                    html.Div(
                        className="login-visual-panel",
                        children=[
                            html.Div(
                                className="login-visual__copy",
                                children=[
                                    html.P(
                                        HERO_HEADLINE,
                                        className="login-visual__headline",
                                    ),
                                    html.P(
                                        HERO_SUPPORT,
                                        className="login-visual__support",
                                    ),
                                ],
                            )
                        ],
                    ),
                ],
            )
        ],
    )
