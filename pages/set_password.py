"""Set-password page — first-time setup and password reset (ADR-033).

Reached only through a one-time link an Administrator hands over
(`/set-password?token=...`). It is a PUBLIC route (the visitor has no session
yet) and is deliberately not in `ROUTE_POLICY`: the token is the whole proof,
and it grants nothing except setting that one account's password.

The page never shows whose account it is, never echoes the token, and answers
every unusable link (unknown, used, expired, revoked) with one message.

Element ids are a callback contract in `callbacks/set_password.py`.
"""
from __future__ import annotations

from dash import dcc, html

from config.settings import auth_settings
from pages.login import LOGO_BLUE_ASSET, LOGO_WHITE_ASSET, _field
from services.account_service import INVALID_LINK_MESSAGE

BODY_ID = "set-password-body"
NEW_ID = "set-password-new"
CONFIRM_ID = "set-password-confirm"
SUBMIT_ID = "set-password-submit"
MESSAGE_ID = "set-password-message"


def invalid_link_body() -> html.Div:
    return html.Div(
        children=[
            html.H1("Link not valid", className="login-heading"),
            html.P(INVALID_LINK_MESSAGE, className="login-support", role="alert"),
        ]
    )


def success_body() -> html.Div:
    return html.Div(
        children=[
            html.H1("Password set", className="login-heading"),
            html.P("Your password has been saved. You can now sign in.", className="login-support"),
            html.A("Go to sign in", href="/", className="login-button", id="set-password-signin-link"),
        ]
    )


def form_body() -> html.Div:
    return html.Div(
        children=[
            html.H1("Choose your password", className="login-heading"),
            html.P(
                f"Use at least {auth_settings.password_min_length} characters. "
                "A passphrase works well.",
                className="login-support",
            ),
            _field(
                "New password",
                NEW_ID,
                dcc.Input(
                    id=NEW_ID, type="password", className="login-input",
                    autoComplete="new-password", n_submit=0,
                ),
            ),
            _field(
                "Confirm password",
                CONFIRM_ID,
                dcc.Input(
                    id=CONFIRM_ID, type="password", className="login-input",
                    autoComplete="new-password", n_submit=0,
                ),
            ),
            html.Button("Set password", id=SUBMIT_ID, className="login-button", n_clicks=0),
        ]
    )


def layout(link_usable: bool) -> html.Div:
    return html.Div(
        className="login-page",
        children=[
            html.Img(src=f"/assets/{LOGO_WHITE_ASSET}", alt="Eskom", className="login-brand-mark"),
            html.Div(
                className="login-stage",
                children=[
                    html.Div(
                        className="login-card",
                        children=[
                            html.Img(src=f"/assets/{LOGO_BLUE_ASSET}", alt="Eskom", className="login-logo-mark"),
                            html.P("RTL Monitoring", className="login-eyebrow"),
                            html.Div(
                                id=BODY_ID,
                                children=[form_body() if link_usable else invalid_link_body()],
                            ),
                            # Outside the swapped body so this output target
                            # always exists, including after a success or an
                            # invalid-link swap.
                            html.Div(id=MESSAGE_ID, className="login-error", role="alert"),
                        ],
                    ),
                ],
            ),
        ],
    )
