"""Application sidebar callbacks — visibility gating, active state, collapse.

Mirrors the equipment selector's pattern: module-level pure functions so they
can be tested without a Dash runtime, `register()` only wires them up.

Three independent concerns, one per callback:
1. Visibility: the sidebar shell is shown only to an authenticated operator.
2. Active state: exactly one sidebar item highlights for the current
   pathname. Derived from the same `routes.parse_pathname` contract the
   router uses, so the sidebar can never disagree with the page that
   rendered about where we are.
3. Collapse: a click on the toggle flips a `dcc.Store`'s boolean, and that
   store drives the sidebar's width, the content region's offset, and the
   toggle button's accessible state together — all three read one source of
   truth so they cannot drift apart.
"""
from __future__ import annotations

from dash import Input, Output, State

from components.app_shell import CONTENT_ID
from components.app_sidebar import (
    COLLAPSE_STORE_ID,
    HIDDEN_STYLE,
    NAV_ID,
    SHELL_ID,
    SIDEBAR_ID,
    TOGGLE_ID,
    sidebar_nav,
)
from routes import parse_pathname

VISIBLE_STYLE: dict = {}

EXPANDED_SIDEBAR_CLASS = "app-sidebar"
COLLAPSED_SIDEBAR_CLASS = "app-sidebar app-sidebar--collapsed"
EXPANDED_CONTENT_CLASS = "app-shell__content"
COLLAPSED_CONTENT_CLASS = "app-shell__content app-shell__content--sidebar-collapsed"

#: route.name -> sidebar item key. "unknown" deliberately has no entry: no
#: page rendered, no item highlighted. The monitoring drill-down (plant,
#: transformer, device) has no top-level destination of its own — it is the
#: monitoring workflow that lives inside Overview — so those routes keep the
#: Overview item highlighted. Assignments has no entry: it has no route in
#: ADMIN-0, so it can never become active.
NAV_KEY_BY_ROUTE: dict[str, str] = {
    "overview": "overview",
    "plant": "overview",
    "transformer": "overview",
    "device": "overview",
    "admin_devices": "devices",
    "device_register": "registration",
    "notifications": "notifications",
    "reports": "reports",
    "admin_users": "users",
}


def _is_authenticated(auth_data) -> bool:
    return bool(auth_data) and bool(auth_data.get("authenticated"))


def _is_collapsed(collapse_data) -> bool:
    return bool(collapse_data) and bool(collapse_data.get("collapsed"))


def sidebar_visibility(auth_data) -> dict:
    """Show the sidebar only to an authenticated operator."""
    return VISIBLE_STYLE if _is_authenticated(auth_data) else dict(HIDDEN_STYLE)


def active_nav_key(pathname: str | None) -> str | None:
    """Which sidebar item is active for this pathname, or None.

    Uses the same `parse_pathname` the router calls, so the highlight tracks
    the page that actually rendered rather than a second copy of the URL
    rules.
    """
    return NAV_KEY_BY_ROUTE.get(parse_pathname(pathname).name)


def toggle_collapsed(n_clicks, collapse_data) -> dict:
    """Flip the collapsed flag on a real click; otherwise pass it through.

    `n_clicks` is 0/None on initial render (no callback fires then, since the
    callback is `prevent_initial_call=True`, but the function stays defensive
    so it is trivially testable on its own).
    """
    collapsed = _is_collapsed(collapse_data)
    if n_clicks:
        collapsed = not collapsed
    return {"collapsed": collapsed}


def sidebar_class(collapse_data) -> str:
    return COLLAPSED_SIDEBAR_CLASS if _is_collapsed(collapse_data) else EXPANDED_SIDEBAR_CLASS


def content_class(collapse_data) -> str:
    return COLLAPSED_CONTENT_CLASS if _is_collapsed(collapse_data) else EXPANDED_CONTENT_CLASS


def toggle_aria_expanded(collapse_data) -> str:
    return "false" if _is_collapsed(collapse_data) else "true"


def toggle_aria_label(collapse_data) -> str:
    return "Expand sidebar" if _is_collapsed(collapse_data) else "Collapse sidebar"


def register(app) -> None:
    """Register sidebar callbacks on the Dash app."""

    @app.callback(
        Output(SHELL_ID, "style"),
        Input("auth-store", "data"),
    )
    def _toggle_visibility(auth_data):
        return sidebar_visibility(auth_data)

    @app.callback(
        Output(NAV_ID, "children"),
        Input("url", "pathname"),
    )
    def _render_active_state(pathname):
        return sidebar_nav(active_nav_key(pathname))

    @app.callback(
        Output(COLLAPSE_STORE_ID, "data"),
        Input(TOGGLE_ID, "n_clicks"),
        State(COLLAPSE_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def _toggle(n_clicks, collapse_data):
        return toggle_collapsed(n_clicks, collapse_data)

    @app.callback(
        Output(SIDEBAR_ID, "className"),
        Output(CONTENT_ID, "className"),
        Output(TOGGLE_ID, "aria-expanded"),
        Output(TOGGLE_ID, "aria-label"),
        Input(COLLAPSE_STORE_ID, "data"),
    )
    def _apply_collapse(collapse_data):
        return (
            sidebar_class(collapse_data),
            content_class(collapse_data),
            toggle_aria_expanded(collapse_data),
            toggle_aria_label(collapse_data),
        )
