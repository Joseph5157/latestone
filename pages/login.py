"""Login page layout — full-bleed hero with a floating card.

Visual refinement only. Every `id` below is a callback contract in
`callbacks/auth.py` and must not be renamed:

    login-username  n_submit (Input), value (State)
    login-password  n_submit (Input), value (State), type (Output)
    toggle-password-btn    n_clicks (Input), aria-label (Output)
    toggle-password-icon   className (Output)
    toggle-password-label  children (Output)
    login-button    n_clicks (Input)
    login-error     children (Output)

`n_submit=0` on both inputs is load-bearing, not decoration. The router inserts
this form dynamically, so the auth callback fires on insertion;
`login_was_submitted` reads all-zero counters as "nobody asked to log in yet".
Dropping the explicit zeros sends `None` instead and re-opens NEW-14, where
every visitor was greeted with "Invalid username or password." before typing.

The password toggle's label is server-rendered ("Show"/"Hide" come from the
callback), so it must stay a text button rather than becoming a CSS-only icon.
The eye glyph is a plain `<span>` nested inside that same button, coloured via
a local SVG used as a CSS mask (see `.toggle-password-icon` in app.css) rather
than an inline image or remote icon font — no outbound request, so the login
control never depends on network access working. Its className is keyed off
the same `showing` boolean as the label and the field's `type` — the callback
writes all three from one value, so they cannot drift apart. The icon carries
`aria-hidden` because the button's accessible name comes from `aria-label`
below, not from flattening the tree's text.
"""
from __future__ import annotations

from dash import dcc, html

HERO_ASSET = "login-powerplant-hero.jpg"
LOGO_BLUE_ASSET = "eskom-logo-blue.webp"
LOGO_WHITE_ASSET = "eskom-logo-white.png"

# Single source for both the initial render and callbacks/auth.py's toggle —
# importing these rather than re-typing the class names is what keeps the
# glyph and the label from ever disagreeing. Each is the full className
# (base + modifier) since the callback replaces `className` wholesale.
TOGGLE_ICON_BASE_CLASS = "toggle-password-icon"
TOGGLE_ICON_SHOW_CLASS = f"{TOGGLE_ICON_BASE_CLASS} {TOGGLE_ICON_BASE_CLASS}--eye"
TOGGLE_ICON_HIDE_CLASS = f"{TOGGLE_ICON_BASE_CLASS} {TOGGLE_ICON_BASE_CLASS}--eye-off"


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
            # Sits over the photo, not the card — the blue logo inside the
            # card below is for a white surface; this is the reversed/white
            # file made for a dark one. Positioned independently of the grid
            # (see .login-brand-mark in app.css) so it holds a fixed corner
            # regardless of how the grid's columns resolve.
            html.Img(
                src=f"/assets/{LOGO_WHITE_ASSET}",
                alt="Eskom",
                className="login-brand-mark",
            ),
            # A two-column grid, not an absolutely/flex-positioned card. The
            # card's own left offset previously had no relationship to
            # anything else on the page — this gives it one: column 1 is sized
            # by `minmax()`, column 2 is left empty on purpose so the plant
            # stays fully visible and unobstructed rather than needing a
            # headline to justify its existence.
            html.Div(
                className="login-stage",
                children=[
                    html.Div(
                        className="login-card",
                        children=[
                            html.Img(
                                src=f"/assets/{LOGO_BLUE_ASSET}",
                                alt="Eskom",
                                className="login-logo-mark",
                            ),
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
                                            [
                                                html.Span(
                                                    html.Span(
                                                        id="toggle-password-icon",
                                                        className=TOGGLE_ICON_SHOW_CLASS,
                                                    ),
                                                    **{"aria-hidden": "true"},
                                                ),
                                                html.Span(
                                                    "Show",
                                                    id="toggle-password-label",
                                                ),
                                            ],
                                            id="toggle-password-btn",
                                            className="toggle-password-btn",
                                            n_clicks=0,
                                            **{"aria-label": "Show password"},
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
                    ),
                ],
            ),
        ],
    )
