"""Application navigation callbacks — visibility gating and active state.

Mirrors the equipment selector's pattern: module-level pure functions so they
can be tested without a Dash runtime, `register()` only wires them up.

Two independent concerns, one per callback:
1. Visibility: the nav shell is shown only to an authenticated operator.
2. Active state: exactly one nav item highlights for the current pathname.
   Derived from the same `routes.parse_pathname` contract the router uses, so
   the nav can never disagree with the page that rendered about where we are.
"""
from __future__ import annotations

from dash import Input, Output

from components.app_navigation import HIDDEN_STYLE, NAV_ID, SHELL_ID, app_navigation
from routes import parse_pathname

VISIBLE_STYLE: dict = {}

#: route.name -> nav item key. "unknown" deliberately has no entry: no page
#: rendered, no nav item highlighted. The monitoring drill-down (plant,
#: transformer, device) has no top-level destination of its own — it is the
#: monitoring workflow that lives inside Overview — so those routes keep the
#: Overview item highlighted.
NAV_KEY_BY_ROUTE: dict[str, str] = {
    "overview": "overview",
    "plant": "overview",
    "transformer": "overview",
    "device": "overview",
    "admin_devices": "devices",
    "reports": "reports",
    "notifications": "notifications",
    "admin_users": "administration",
}


def _is_authenticated(auth_data) -> bool:
    return bool(auth_data) and bool(auth_data.get("authenticated"))


def nav_visibility(auth_data) -> dict:
    """Show the app nav only to an authenticated operator."""
    return VISIBLE_STYLE if _is_authenticated(auth_data) else dict(HIDDEN_STYLE)


def active_nav_key(pathname: str | None) -> str | None:
    """Which nav item is active for this pathname, or None.

    Uses the same `parse_pathname` the router calls, so the highlight tracks
    the page that actually rendered rather than a second copy of the URL rules.
    """
    return NAV_KEY_BY_ROUTE.get(parse_pathname(pathname).name)


def register(app) -> None:
    """Register application navigation callbacks on the Dash app."""

    @app.callback(
        Output(SHELL_ID, "style"),
        Input("auth-store", "data"),
    )
    def _toggle_visibility(auth_data):
        return nav_visibility(auth_data)

    @app.callback(
        Output(NAV_ID, "children"),
        Input("url", "pathname"),
    )
    def _render_active_state(pathname):
        return app_navigation(active_nav_key(pathname))