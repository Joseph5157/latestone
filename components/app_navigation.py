"""Application-level navigation — mounted once, in the global app layout.

Separate from equipment navigation (components.equipment_selector): the app
nav is the set of top-level application destinations (Overview, Devices,
Reports, Notifications, Administration), while the equipment selector is the
Plant -> Transformer -> Device jump tool used inside monitoring context.

Mounted once in `app.layout`, hidden on login, same pattern as the equipment
selector: its callbacks (callbacks.navigation) fire on every route, so their
targets must exist no matter which page is rendered.

The monitoring workflow is deliberately not a top-level destination: the
Fleet -> Plant -> Transformer -> Device hierarchy and the equipment selector
are the workflow. The drill-down pages render under Overview, so the Overview
item stays highlighted while an operator works through them. A distinct
Monitoring landing page can be added back as a nav item only if one is
actually built.
"""
from __future__ import annotations

from dash import dcc, html

SHELL_ID = "app-nav-shell"
NAV_ID = "app-navigation"

#: (key, label, href). Key is the identity the active-state logic joins on;
#: label is what the operator sees; href is the destination route.
NAV_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("overview", "Overview", "/plants"),
    ("devices", "Devices", "/admin/devices"),
    ("reports", "Reports", "/reports"),
    ("notifications", "Notifications", "/notifications"),
    ("administration", "Administration", "/admin/users"),
)

HIDDEN_STYLE = {"display": "none"}


def app_navigation(active_key: str | None) -> html.Nav:
    """Render the application nav with at most one active link.

    The active link is marked with the `--active` modifier class (for styling).
    `aria-current="page"` sits on the wrapping `<li>`, not the `dcc.Link`:
    Dash's `dcc.Link` (2.17) accepts a fixed prop set and rejects `aria-*`
    keywords, while the html components take them as wildcards. The `<li>` is
    the nav item, so "current page" is correctly announced from it.
    """
    items = []
    for key, label, href in NAV_ITEMS:
        is_active = key == active_key
        className = "app-nav__link"
        item_props = {}
        if is_active:
            className += " app-nav__link--active"
            item_props = {"aria-current": "page"}
        items.append(
            html.Li(
                dcc.Link(label, href=href, className=className),
                className="app-nav__item",
                **item_props,
            )
        )
    return html.Nav(
        children=html.Ul(children=items, className="app-nav"),
        id=NAV_ID,
    )


def app_navigation_shell() -> html.Div:
    """Global wrapper whose `style` the auth callback toggles.

    Starts hidden: the first paint is always the login page, and the nav must
    not flash above the hero before authentication runs.
    """
    return html.Div(
        id=SHELL_ID,
        className="app-nav-shell",
        style=dict(HIDDEN_STYLE),
        children=[app_navigation(None)],
    )