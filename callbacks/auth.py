"""Authentication callbacks — isolated so they can later be replaced."""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update

from pages.login import TOGGLE_ICON_HIDE_CLASS, TOGGLE_ICON_SHOW_CLASS
from routes import legacy_redirect_path
from services import auth_service, login_security, login_service

logger = logging.getLogger(__name__)


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

#: ADR-033. Shown when this login name is inside a back-off window. It is keyed
#: on the typed name whether or not the account exists, so it reveals nothing
#: about which names exist, and it names neither a count nor a duration.
LOGIN_THROTTLED_MESSAGE = "Too many sign-in attempts. Please wait a few minutes and try again."


def login_outputs(username, password) -> tuple[str, object]:
    """(error message, auth-store payload) for one submitted login.

    The callback body as a pure function, so the identity written into the
    session is testable without a Dash runtime — the same shape
    `callbacks.listings` uses for its row builders.

    On failure the store is left alone rather than reset: a failed attempt
    should not sign out a session that is already open in another tab.
    """
    outcome = login_service.attempt_login(username, password)
    if outcome.user is None:
        return (
            LOGIN_THROTTLED_MESSAGE if outcome.throttled else LOGIN_FAILED_MESSAGE
        ), no_update
    return "", auth_service.to_session(outcome.user)


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


#: The address operators type or bookmark to sign in. It is NOT a route:
#: `parse_pathname` returns `unknown` for it, and the router never dispatches
#: on it — the login form is what `callbacks/routing.py` substitutes for
#: WHATEVER path was asked for when there is no trusted identity, which is
#: also what lets a deep link survive signing in.
#:
#: That substitution is why this constant has to exist. Signed out, `/login`
#: renders the form like any other path, so the app teaches an operator that
#: `/login` is a real address; signed in, the same address fell through the
#: dispatch chain to `not_found_panel("page")` — the answer a typo gets. One
#: URL, two contradictory answers, and only this half can move: the signed-out
#: half is every path, not this one.
LOGIN_PATH = "/login"


def login_path_redirect(pathname, user):
    """Where `/login` sends someone who is already signed in, or `no_update`.

    `/` rather than a named page, deliberately: `landing_route_name` already
    decides that Administrators and Technicians land on the Command Center and
    everyone else on Fleet Overview. Naming a destination here would be a
    second place that decides where a role lands, free to disagree with the
    first.

    Guarded on the identity, not just the path. Returning `/` for a signed-out
    visitor would bounce them off the one page they actually need, since the
    router is rendering the login form at this very path.

    Takes the resolved identity as an argument rather than calling
    `current_identity()` itself — the caller has already paid for that lookup,
    and a helper that answers from its arguments alone is one the tests can
    ask about every path without a session.
    """
    if pathname != LOGIN_PATH or user is None:
        return no_update
    return "/"


def reconciled_auth_store(pathname, auth_data, user):
    """The auth-store payload that matches the trusted session, or no_update.

    The router decides login-vs-page from the server session; the sidebar,
    the Asset Navigator and the header read `auth-store`. When the two drift
    — the server session is gone after an app restart (a fresh secret key),
    a logout in another tab, a deactivation — the router shows the login
    page while the chrome still shows a signed-in sidebar. The reverse drift
    (a new tab: empty store, valid cookie) shows a page with no sidebar.
    Rewriting the store from the server's answer makes every reader agree.

    `/logout` is skipped: `_sign_out` owns that navigation, and this call's
    request may still carry the cookie `_sign_out` is about to clear, which
    would write the signed-out session straight back in.
    """
    if pathname == LOGOUT_PATH:
        return no_update
    wanted = auth_service.to_session(user) if user is not None else {"authenticated": False}
    return no_update if auth_data == wanted else wanted


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
        error, session_payload = login_outputs(username, password)
        # AUTH-HARDEN-1: the trusted server session is established HERE, inside
        # the real callback dispatch (a Flask request), from the user_id
        # `login_outputs` just resolved server-side — never from anything the
        # browser has sent back. `login_outputs` itself stays a pure function
        # so its existing tests need no Flask request context.
        if session_payload is not no_update:
            auth_service.start_trusted_session(session_payload["user_id"])
        return error, session_payload

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
        # render, which this needs — /logout and /login both arrive as page
        # loads, typed or bookmarked rather than navigated to.
        prevent_initial_call="initial_duplicate",
    )
    def _path_command(pathname):
        """The paths that are commands rather than pages.

        `/logout` ends a session; `/login` is the address operators type to
        start one. Neither is a route — `parse_pathname` returns `unknown`
        for both, and the router dispatches on neither. RTL-LIST-ROUTE-01
        adds the legacy `/plants` list address, rewritten to `/rtls`.

        ONE callback, not two, and that is forced rather than chosen. Dash
        derives an `allow_duplicate` output's id from a hash of the INPUTS
        alone (`dash/_utils.py:create_callback_id`), so a second callback
        writing `url.pathname` off this same single `Input("url",
        "pathname")` generates a byte-identical output id and the app dies
        at import with "Duplicate callback outputs". Splitting these would
        mean giving one of them an extra input that nothing reads, purely to
        perturb a hash. They belong together anyway: both answer "this path
        is an instruction, not a page."
        """
        if pathname == LOGOUT_PATH:
            # ADR-033: audit who signed out BEFORE the session is cleared.
            # Best effort — signing out always completes.
            try:
                signing_out = auth_service.current_identity()
                if signing_out is not None:
                    login_security.register_logout(signing_out.user_id)
            except Exception:
                logger.exception("Could not audit the sign-out")
            # AUTH-HARDEN-1: clears the trusted server session, not just the
            # browser's auth-store.
            auth_service.end_trusted_session()
            return sign_out_outputs(pathname)

        if pathname == LOGIN_PATH:
            # Asks the server session, not `auth-store`: this decides a
            # navigation, and AUTH-HARDEN-1's rule is that anything the
            # browser can edit never decides one.
            try:
                user = auth_service.current_identity()
            except Exception:
                # Cannot tell who is asking: leave the path alone and let the
                # router answer it. It falls back to the login form when it
                # cannot resolve an identity either, which is the safe answer.
                logger.exception("Could not resolve the trusted session for %r", pathname)
                return no_update, no_update
            return no_update, login_path_redirect(pathname, user)

        # RTL-LIST-ROUTE-01: a compatibility address is a third instruction
        # rather than a page — `/plants` means "go to `/rtls`". It lives in
        # this callback because it must: see the docstring on why a second
        # `url.pathname` writer off this Input cannot exist. Only the path is
        # written, so `url.search` — and any query a legacy link carried — is
        # kept. No identity is consulted: this names an address and decides
        # nothing; `/rtls` is authorized by the router like any other path.
        canonical = legacy_redirect_path(pathname)
        if canonical is not None:
            return no_update, canonical

        # Every other path: not this callback's business. `sign_out_outputs`
        # is the one that already says so, rather than a second literal pair
        # of `no_update`s that could drift from it.
        return sign_out_outputs(pathname)

    @app.callback(
        Output("auth-store", "data", allow_duplicate=True),
        Input("url", "pathname"),
        Input("auth-store", "data"),
        # Fires on the first render too: an app restart invalidates the
        # cookie, and the very next page load is where the drift shows.
        prevent_initial_call="initial_duplicate",
    )
    def _reconcile_auth_store(pathname, auth_data):
        # Its own output is also an Input, which Dash allows within one
        # callback; it settles in one step because a rewritten store equals
        # `wanted` on the re-fire and returns no_update.
        try:
            user = auth_service.current_identity()
        except Exception:
            # Cannot tell who is signed in: leave the store alone rather than
            # sign anyone out on a transient database error.
            logger.exception("Could not resolve the trusted session")
            return no_update
        return reconciled_auth_store(pathname, auth_data, user)

    # Logout stays a plain `<a href="/logout">` (see components.app_header).
    # That makes it a full page load, so the callback above must run on its
    # initial call — a route-change-only callback would never see it. It also
    # means a bookmarked /logout signs out rather than rendering nothing.
