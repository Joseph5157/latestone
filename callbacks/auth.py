"""Authentication callbacks — isolated so they can later be replaced."""
from __future__ import annotations

from dash import Input, Output, State, no_update

from pages.login import TOGGLE_ICON_HIDE_CLASS, TOGGLE_ICON_SHOW_CLASS
from services import auth_service


def login_was_submitted(n_clicks, username_submits, password_submits) -> bool:
    """Whether the operator actually asked to log in.

    Counts the button and both Enter presses. Must stay false when every
    counter is 0: the router inserts the login form dynamically, so the
    callback fires on insertion with the layout's zeros. `prevent_initial_call`
    only suppresses the app's very first load, so an `is None` check let that
    through and greeted every visitor with "Invalid username or password."
    before they had typed anything.
    """
    return any(bool(counter) for counter in (n_clicks, username_submits, password_submits))


#: One message for every refusal. `auth_service.authenticate` already returns
#: the same None whether the password was wrong, the account was deactivated or
#: no such user exists; repeating that discipline here keeps the form from
#: leaking the difference through its wording.
LOGIN_FAILED_MESSAGE = "Invalid username or password."


def login_outputs(username, password) -> tuple[str, object]:
    """(error message, auth-store payload) for one submitted login.

    The callback body as a pure function, so the identity written into the
    session is testable without a Dash runtime — the same shape
    `callbacks.listings` uses for its row builders.

    On failure the store is left alone rather than reset: a failed attempt
    should not sign out a session that is already open in another tab.
    """
    user = auth_service.authenticate(username, password)
    if user is None:
        return LOGIN_FAILED_MESSAGE, no_update
    return "", auth_service.to_session(user)


#: Where the header's Logout link points. A path rather than a route name:
#: it renders no page, it ends one.
LOGOUT_PATH = "/logout"


def sign_out_outputs(pathname):
    """(auth-store payload, redirect) for one navigation.

    Signing out used to be a side effect of geometry: `auth-store` was
    memory-backed, so the Logout anchor's full page load discarded it. Once
    the store survives a reload — which is what stops an ordinary refresh
    signing the user out — that no longer happens, and the session has to be
    cleared deliberately.

    Returns the initial payload rather than an empty dict: `{"authenticated":
    False}` is the same shape the layout starts from, so a signed-out session
    is indistinguishable from one that never signed in.
    """
    if pathname != LOGOUT_PATH:
        return no_update, no_update
    return {"authenticated": False}, "/"


def password_toggle_state(n_clicks) -> tuple[str, str, str, str]:
    """(field type, icon className, label, accessible name) for the current
    click count.

    One boolean drives all four so the glyph, the word and the accessible
    name can never disagree with each other or with the field they describe.
    """
    showing = bool(n_clicks) and n_clicks % 2 == 1
    if showing:
        return "text", TOGGLE_ICON_HIDE_CLASS, "Hide", "Hide password"
    return "password", TOGGLE_ICON_SHOW_CLASS, "Show", "Show password"


def register(app) -> None:
    """Register auth callbacks on the Dash app."""

    @app.callback(
        Output("login-error", "children"),
        Output("auth-store", "data"),
        Input("login-button", "n_clicks"),
        Input("login-username", "n_submit"),
        Input("login-password", "n_submit"),
        State("login-username", "value"),
        State("login-password", "value"),
        prevent_initial_call=True,
    )
    def handle_login(n_clicks, username_submits, password_submits, username, password):
        # Deliberately does not redirect: leaving `url.pathname`/`search` untouched
        # means a successful login re-triggers routing (auth-store is a routing
        # Input) on whatever URL the user actually requested, including deep links.
        # Enter in either field submits, same as the button — the inputs already
        # declared n_submit but nothing listened to it.
        if not login_was_submitted(n_clicks, username_submits, password_submits):
            return no_update, no_update
        # Credential checking AND identity resolution stay behind auth_service
        # so swapping in the client's real authentication needs no change to
        # callback code. The store now carries the full identity (ROLE-1); the
        # `authenticated` flag other callbacks read is unchanged.
        return login_outputs(username, password)

    @app.callback(
        Output("login-password", "type"),
        Output("toggle-password-icon", "className"),
        Output("toggle-password-label", "children"),
        Output("toggle-password-btn", "aria-label"),
        Input("toggle-password-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_password_visibility(n_clicks):
        return password_toggle_state(n_clicks)

    @app.callback(
        Output("auth-store", "data", allow_duplicate=True),
        Output("url", "pathname", allow_duplicate=True),
        Input("url", "pathname"),
        # Not False: Dash refuses `allow_duplicate` with an unguarded initial
        # call. "initial_duplicate" is the form that still fires on the first
        # render, which this needs — /logout arrives as a page load.
        prevent_initial_call="initial_duplicate",
    )
    def _sign_out(pathname):
        return sign_out_outputs(pathname)

    # Logout stays a plain `<a href="/logout">` (see components.app_header).
    # That makes it a full page load, so the callback above must run on its
    # initial call — a route-change-only callback would never see it. It also
    # means a bookmarked /logout signs out rather than rendering nothing.
