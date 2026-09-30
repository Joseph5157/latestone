"""Primary application navigation — a persistent, collapsible left sidebar.

Mounted once, in the global app layout (see components.app_shell), replacing
the horizontal app-navigation bar as the application's one primary navigation
system. Separate from the equipment selector (components.equipment_selector):
the sidebar is the set of top-level application destinations, while the
equipment selector is the Plant -> Transformer -> Device jump tool used
inside monitoring context — that split is unchanged by this phase.

The monitoring workflow is deliberately not a top-level destination: the
legacy synthetic Plant -> Transformer -> Device hierarchy and the equipment
selector are that workflow. Those drill-down pages still resolve to the
`overview` nav key, so its item stays highlighted while an operator works
through them (routes.NAV_KEY_BY_ROUTE).

CLIENT-TERMINOLOGY-NAV-01: that item is now labelled "Registered RTLs",
because it shows the client's registered RTL directory (now at `/rtls`). The synthetic
drill-down is no longer reachable from it (the RTL fleet table links nowhere)
and the Asset Navigator is already hidden on that route
(callbacks.navigation.UTILITY_ROUTES), so the highlight is the last place
those two meet — retiring that join belongs to the gate that retires the
synthetic pages themselves, not to a wording gate.

Assignments (ADMIN-ASSIGN-1) now has a real route, `/admin/assignments` — a
technician workload roster (who has how many RTLs) plus the same
Assign/Manage table Device Management offers, reusing the shared
assign/manage drawers rather than a third copy of that workflow. It was
routeless from ADMIN-0 until this gate specifically because no page existed
yet to point it at.

ROLE-2: the item set is filtered by the signed-in role, derived from the route
policy in services.authorization. Hiding is not enforcement — callbacks.routing
refuses the route itself; this only stops the sidebar advertising somewhere the
operator cannot go.

ADMIN-0P (sidebar polish): each item carries a local SVG icon, rendered in
front of the label in both expanded and collapsed states — the collapsed
rail used to fall back to a two-letter abbreviation ("NO" for Notifications
read as the word "no" in review), which read as a placeholder rather than
finished chrome. The icon reuses the same technique as pages/login.py's eye
toggle: an empty `<span>` whose shape comes from a local SVG loaded as a CSS
mask (`.app-sidebar__icon` in app.css) and whose colour comes from
`background-color: currentColor`, so every existing text-colour state
(default/hover/active/disabled/focus) paints the icon for free with no extra
state logic. No icon library, no CDN, no emoji — the files live in
assets/icons/ alongside eye.svg/eye-off.svg. The icon is `aria-hidden`; the
link's accessible name is still its text label, and each link keeps its
native `title` tooltip (useful when collapsed, where the label is visually
hidden but still in the DOM).
"""
from __future__ import annotations

from dash import dcc, html

from components.theme import theme_toggle
from routes import RTL_LIST_PATH, RTL_NETWORK_PATH
from services.authorization import visible_nav_keys

SHELL_ID = "app-sidebar-shell"
LOGOUT_PATH = "/logout"
SIDEBAR_ID = "app-sidebar"
NAV_ID = "app-sidebar-nav"
TOGGLE_ID = "app-sidebar-toggle"
COLLAPSE_STORE_ID = "sidebar-collapse-store"

HIDDEN_STYLE = {"display": "none"}

#: (key, label, href, icon). `key` is the identity the active-state logic
#: joins on; `icon` is the assets/icons/nav-{icon}.svg slug rendered before
#: `label` in every state. Every current item has a real route — the
#: `key is None`/`href is None` routeless-placeholder shape this type used
#: to also describe (Assignments, before ADMIN-ASSIGN-1) is gone now that
#: nothing uses it; re-add it here and in `_permitted_items`/`sidebar_nav`
#: if a future item genuinely has no page of its own again.
SidebarItem = tuple[str, str, str, str]

#: (section_title, items). The first section has no title (Overview stands
#: alone, matching the fleet overview's status as the operator landing page).
SIDEBAR_SECTIONS: tuple[tuple[str | None, tuple[SidebarItem, ...]], ...] = (
    (None, (
        # CLIENT-TERMINOLOGY-NAV-01: the label is the client's word for what
        # this route shows — the registered RTL directory read from the client
        # SQL Server. The key is deliberately untouched: `overview` is the
        # routing/authorization identity (routes.NAV_KEY_BY_ROUTE,
        # services.authorization.ROUTE_POLICY).
        # RTL-LIST-ROUTE-01: the href is the canonical `/rtls`. `/plants`
        # still arrives there, but only for old links — never for new ones.
        ("overview", "Registered RTLs", RTL_LIST_PATH, "overview"),
        # LATEST-NETWORK-CONTEXT-01: visible only to the roles allowed to open
        # the route (derived from ROUTE_POLICY, never restated here).
        ("network", "Network", RTL_NETWORK_PATH, "network"),
        ("command_center", "Command Center", "/command-center", "command-center"),
    )),
    ("Operations", (
        ("devices", "Devices", "/admin/devices", "devices"),
        # A Technician's own assigned-devices page (ADR-016). Same label and
        # icon concept as the Administrator's "Devices" above, deliberately:
        # ROUTE_POLICY makes the two routes mutually exclusive per role, so
        # exactly one of these two items is ever visible to a given session
        # — never both, never neither, for anyone with device access at all.
        ("technician_devices", "Devices", "/devices", "my-devices"),
        ("assignments", "Assignments", "/admin/assignments", "assignments"),
        ("registration", "Registration", "/admin/devices/new", "registration"),
    )),
    ("System", (
        ("notifications", "Notifications", "/notifications", "notifications"),
        ("reports", "Reports", "/reports", "reports"),
        ("users", "Users", "/admin/users", "users"),
        ("audit_log", "Audit Log", "/admin/audit-log", "audit-log"),
        ("settings", "Settings", "/admin/settings", "settings"),
    )),
)


def _item_content(label: str, icon: str) -> list:
    return [
        html.Span(
            className=f"app-sidebar__icon app-sidebar__icon--{icon}",
            **{"aria-hidden": "true"},
        ),
        html.Span(label, className="app-sidebar__label"),
    ]


def _permitted_items(section_items, role: str | None) -> tuple[SidebarItem, ...]:
    """The items in this section `role` may see (ROLE-2).

    Visibility is derived from the route policy, never restated here — an item
    shows exactly when the role may open the route behind it, so a visible
    item that refuses to open is not expressible.
    """
    visible = visible_nav_keys(role)
    return tuple(item for item in section_items if item[0] in visible)


def sidebar_nav(active_key: str | None, role: str | None = None) -> html.Ul:
    """Render the sidebar's item list with at most one active link.

    Mirrors the retired app_navigation's convention: the active link carries
    the `--active` modifier class, and `aria-current="page"` sits on the
    wrapping `<li>` (dcc.Link has a fixed prop set and does not accept
    wildcard `aria-*` keywords; the `<li>` is the nav item, so "current page"
    is correctly announced from it).

    `role` filters the items (ROLE-2). It defaults to None — no role, no
    navigation — so the pre-authentication shell renders an empty nav rather
    than the full one behind a hidden container. A section whose items are all
    filtered out loses its heading too; a standing "Operations" title over
    nothing reads as a section that failed to load.

    Hiding is not the enforcement. `callbacks.routing` refuses the route
    itself; this only stops the sidebar advertising somewhere the operator
    cannot go.
    """
    items = []
    for section_title, section_items in SIDEBAR_SECTIONS:
        section_items = _permitted_items(section_items, role)
        if not section_items:
            continue
        if section_title is not None:
            items.append(
                html.Li(section_title, className="app-sidebar__section-label")
            )
        for key, label, href, icon in section_items:
            is_active = key == active_key
            className = "app-sidebar__link"
            item_props = {}
            if is_active:
                className += " app-sidebar__link--active"
                item_props = {"aria-current": "page"}
            items.append(
                html.Li(
                    dcc.Link(
                        _item_content(label, icon),
                        href=href,
                        className=className,
                        title=label,
                    ),
                    className="app-sidebar__item",
                    **item_props,
                )
            )
    return html.Ul(children=items, className="app-sidebar__nav")


def app_sidebar(active_key: str | None = None, role: str | None = None) -> html.Aside:
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
            # Named because the breadcrumb is a second `<nav>` on every
            # page; unnamed, the two landmarks announce identically.
            html.Nav(
                children=sidebar_nav(active_key, role),
                id=NAV_ID,
                **{"aria-label": "Main"},
            ),
            # Sign-out lives here rather than in app_header: the header is
            # rendered per page (and Command Center renders none at all),
            # so a header-only Logout is present or absent depending on
            # which page you happen to be on. The sidebar is mounted once
            # globally and hidden wholesale when signed out, so this is
            # visible exactly when it is usable.
            #
            # NOT in SIDEBAR_SECTIONS: that tuple is the role-filtered
            # ROUTE_POLICY-derived navigation, and every key in it must map
            # to a route someone may open (tests/test_authorization.py
            # asserts exactly that). Logout is an action, not a
            # destination, and is available to every signed-in role.
            #
            # A plain anchor, deliberately: the full page load is what lets
            # callbacks.auth._sign_out fire on its initial call, and what
            # makes a bookmarked /logout sign out rather than render
            # nothing (callbacks/auth.py:132).
            html.Div(
                [theme_toggle(), html.A(
                    _item_content("Logout", "logout"),
                    href=LOGOUT_PATH,
                    className="app-sidebar__link app-sidebar__logout",
                    title="Logout",
                )],
                className="app-sidebar__footer",
            ),
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
