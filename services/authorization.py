"""
Route and navigation authorization (ROLE-2).

Pure policy. No database, no Dash, no I/O — it answers "may this role open
this route" and nothing else, so the answer is the same wherever it is asked
and can be tested without a runtime.

THE POLICY TABLE IS THE SOURCE OF TRUTH. Navigation is derived from it
(`visible_nav_keys`), never maintained alongside it. Two tables would each
pass their own tests while contradicting each other, and the contradiction
shows up as the two defects this arrangement makes impossible: a sidebar item
you can see and cannot open, and a page you may open with no way to reach it.

DEFAULT DENY. A route name absent from `ROUTE_POLICY` is denied to every role.
A route added later is unreachable until someone lists it deliberately — the
test suite says so out loud, so adding a route without a policy entry fails
rather than ships. `unknown` is deliberately not in the table: it is not an
application route, and the router keeps "no such page" and "not for you"
apart.

WHAT THIS IS NOT. This is an application-level control. The router refuses,
but the data callbacks still answer whoever asks, and the role itself travels
in a browser-side `dcc.Store` a client can set (S-4/S-5 in
docs/CODE_AUDIT.md). ROLE-2 shapes what the UI offers; it does not withhold
data from anyone bypassing the UI. Calling any of this production-secure needs
the server-verifiable session that work is blocked on.

SCOPE. Routes only. Device-level scope — a technician seeing only their
assigned RTLs, and which actions each role may take on a device — is ROLE-3,
deliberately kept out so route policy and row-level policy do not braid
together in one table.
"""
from __future__ import annotations

from routes import NAV_KEY_BY_ROUTE
from services.prototype_users import CONFIRMED_ROLES

ADMINISTRATOR = "administrator"
TECHNICIAN = "technician"
GENERAL = "general"

#: Guards the join to the persisted vocabulary. A role string that drifts from
#: `users.role` would deny everyone silently, which is safe but baffling.
assert {ADMINISTRATOR, TECHNICIAN, GENERAL} == set(CONFIRMED_ROLES)

_EVERY_ROLE = frozenset(CONFIRMED_ROLES)
_ADMIN_ONLY = frozenset({ADMINISTRATOR})

#: `routes.Route.name` -> the roles allowed to open it.
#:
#: Technician and General are identical here ON PURPOSE. They diverge in
#: ROLE-3 at device scope and action authorization — Technician gains
#: operational capability over assigned RTLs, General stays read-only — and
#: inventing a route-level difference now would be something ROLE-3 has to
#: undo. Equal is a decision, not an oversight.
ROUTE_POLICY: dict[str, frozenset[str]] = {
    # Monitoring: the fleet and the drill-down through it. Open to everyone
    # who is signed in — reading the plant hierarchy is the application's
    # baseline purpose, not a privilege.
    "overview": _EVERY_ROLE,
    "plant": _EVERY_ROLE,
    "transformer": _EVERY_ROLE,
    "device": _EVERY_ROLE,
    "notifications": _EVERY_ROLE,
    "reports": _EVERY_ROLE,
    # Administration: managing what exists and who exists.
    "admin_devices": _ADMIN_ONLY,
    "device_register": _ADMIN_ONLY,
    "admin_users": _ADMIN_ONLY,
}


def may_access_route(role, route_name: str) -> bool:
    """Whether `role` may open `route_name`.

    Compared exactly, never case-folded: `"Administrator"` is not the
    administrator. A role that is None, blank, unrecognised or not even a
    string reaches nothing, so a malformed session degrades to no access
    rather than to a default one.
    """
    if not isinstance(role, str):
        return False
    return role in ROUTE_POLICY.get(route_name, frozenset())


def visible_nav_keys(role) -> frozenset[str]:
    """The sidebar item keys `role` may see.

    Derived from `ROUTE_POLICY` via the route -> nav-key map, so an item is
    visible exactly when at least one route behind it is permitted. That map
    lives in `routes` alongside the URL rules — a routing fact, shared by the
    sidebar and by this policy, rather than something a service reaches into
    `callbacks/` to borrow.
    """
    return frozenset(
        key
        for route_name, key in NAV_KEY_BY_ROUTE.items()
        if may_access_route(role, route_name)
    )
