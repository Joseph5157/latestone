"""Primary application navigation — a persistent, collapsible left sidebar.

Mounted once, in the global app layout (see components.app_shell), replacing
the horizontal app-navigation bar as the application's one primary navigation
system. Separate from the equipment selector (components.equipment_selector):
the sidebar is the set of top-level application destinations, while the
equipment selector is the Plant -> Transformer -> Device jump tool used
inside monitoring context — that split is unchanged by this phase.

The monitoring workflow is deliberately not a top-level destination: the
Fleet -> Plant -> Transformer -> Device hierarchy and the equipment selector
are the workflow. The drill-down pages render under Overview, so the
Overview item stays highlighted while an operator works through them.

Assignments has no standalone route yet (ADMIN-0 explicitly does not build
one — see callbacks.navigation.NAV_KEY_BY_ROUTE and the ADMIN-0 report for
the reasoning). It renders as a disabled, non-destructive item rather than a
dead link or an invented page.

No icon library exists anywhere in this codebase (the one precedent,
pages/login.py's eye toggle, is a local SVG used as a CSS mask for a single
control). Rather than introduce a new icon dependency for seven nav items,
the collapsed state uses a two-letter text abbreviation plus a native
`title` tooltip on each link — no images, no emoji, no external font.
"""
from __future__ import annotations

from dash import dcc, html

SHELL_ID = "app-sidebar-shell"
SIDEBAR_ID = "app-sidebar"
NAV_ID = "app-sidebar-nav"
TOGGLE_ID = "app-sidebar-toggle"
COLLAPSE_STORE_ID = "sidebar-collapse-store"

HIDDEN_STYLE = {"display": "none"}

#: (key, label, href, abbr). `key` is the identity the active-state logic
#: joins on (None for items with no route of their own); `abbr` is what
#: renders in place of `label` when the sidebar is collapsed.
SidebarItem = tuple[str | None, str, str | None, str]

#: (section_title, items). The first section has no title (Overview stands
#: alone, matching the fleet overview's status as the operator landing page).
SIDEBAR_SECTIONS: tuple[tuple[str | None, tuple[SidebarItem, ...]], ...] = (
    (None, (
        ("overview", "Overview", "/plants", "OV"),
    )),
    ("Operations", (
        ("devices", "Devices", "/admin/devices", "DE"),
        (None, "Assignments", None, "AS"),
        ("registration", "Registration", "/admin/devices/new", "RE"),
    )),
    ("System", (
        ("notifications", "Notifications", "/notifications", "NO"),
        ("reports", "Reports", "/reports", "RP"),
        ("users", "Users", "/admin/users", "US"),
    )),
)


def _item_content(label: str, abbr: str) -> list:
    return [
        html.Span(abbr, className="app-sidebar__abbr", **{"aria-hidden": "true"}),
        html.Span(label, className="app-sidebar__label"),
    ]


def sidebar_nav(active_key: str | None) -> html.Ul:
    """Render the sidebar's item list with at most one active link.

    Mirrors the retired app_navigation's convention: the active link carries
    the `--active` modifier class, and `aria-current="page"` sits on the
    wrapping `<li>` (dcc.Link has a fixed prop set and does not accept
    wildcard `aria-*` keywords; the `<li>` is the nav item, so "current page"
    is correctly announced from it).
    """
    items = []
    for section_title, section_items in SIDEBAR_SECTIONS:
        if section_title is not None:
            items.append(
                html.Li(section_title, className="app-sidebar__section-label")
            )
        for key, label, href, abbr in section_items:
            if href is None:
                items.append(
                    html.Li(
                        html.Span(
                            _item_content(label, abbr),
                            className="app-sidebar__link app-sidebar__link--disabled",
                            title=f"{label} — manage from Devices",
                            **{"aria-disabled": "true"},
                        ),
                        className="app-sidebar__item",
                    )
                )
                continue

            is_active = key == active_key
            className = "app-sidebar__link"
            item_props = {}
            if is_active:
                className += " app-sidebar__link--active"
                item_props = {"aria-current": "page"}
            items.append(
                html.Li(
                    dcc.Link(
                        _item_content(label, abbr),
                        href=href,
                        className=className,
                        title=label,
                    ),
                    className="app-sidebar__item",
                    **item_props,
                )
            )
    return html.Ul(children=items, className="app-sidebar__nav")


def app_sidebar(active_key: str | None = None) -> html.Aside:
    return html.Aside(
        id=SIDEBAR_ID,
        className="app-sidebar",
        children=[
            html.Button(
                html.Span(className="app-sidebar__toggle-icon", **{"aria-hidden": "true"}),
                id=TOGGLE_ID,
                type="button",
                className="app-sidebar__toggle",
                **{"aria-expanded": "true", "aria-label": "Collapse sidebar"},
            ),
            html.Nav(children=sidebar_nav(active_key), id=NAV_ID),
        ],
    )


def app_sidebar_shell() -> html.Div:
    """Global wrapper whose `style` the auth callback toggles.

    Starts hidden: the first paint is always the login page, and the sidebar
    must not flash above the hero before authentication runs. Same pattern
    as the equipment selector and the retired app-navigation shell.
    """
    return html.Div(
        id=SHELL_ID,
        className="app-sidebar-shell",
        style=dict(HIDDEN_STYLE),
        children=[
            dcc.Store(id=COLLAPSE_STORE_ID, storage_type="session", data={"collapsed": False}),
            app_sidebar(None),
        ],
    )
