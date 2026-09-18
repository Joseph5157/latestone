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

WHAT THIS IS NOT. This is a pure policy table, not the identity source. The
browser-side `auth-store` (`dcc.Store`) a client can set is presentation
only — it drives which nav items and controls render, nothing more.
Authorization decisions call this table with the CURRENT trusted identity
(`services.auth_service.current_identity()`, resolved fresh from the `users`
row on every protected operation), never with anything read from `auth-store`
(AUTH-HARDEN-1/1R closed S-4/S-5 in docs/CODE_AUDIT.md on that basis). This
module still answers only "may this role reach this route" — role resolution,
scope, and the per-callback guard calls are each some other module's job.

SCOPE. Routes, page-content capabilities, and actions — three dimensions,
three tables, deliberately not derived from one another. Navigation IS
derived from routes because it is the same question viewed twice; a
capability is not. Device VISIBILITY is not here at all: it belongs to
services/device_scope.py, which is the only answer to "may this user see
this RTL?". This module stays pure — no database, no Dash — which is why the
action guard that needs an assignment read lives elsewhere.
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
_OPERATIONAL_ROLES = frozenset({ADMINISTRATOR, TECHNICIAN})
_TECHNICIAN_ONLY = frozenset({TECHNICIAN})

#: `routes.Route.name` -> the roles allowed to open it.
#:
#: Functional Specification §5.9 limits General User to log-on, transformer
#: data, and export. Monitoring hierarchy routes and reports stay available;
#: operational Notifications and Command Center surfaces are limited to
#: administrators and technicians. This route boundary controls both direct
#: URL enforcement and sidebar filtering.
ROUTE_POLICY: dict[str, frozenset[str]] = {
    # Monitoring: the fleet and the drill-down through it. Open to everyone
    # who is signed in — reading the plant hierarchy is the application's
    # baseline purpose, not a privilege.
    "overview": _EVERY_ROLE,
    "plant": _EVERY_ROLE,
    "transformer": _EVERY_ROLE,
    "device": _EVERY_ROLE,
    "notifications": _OPERATIONAL_ROLES,
    "reports": _EVERY_ROLE,
    "command_center": _OPERATIONAL_ROLES,
    "command_center_locations": _OPERATIONAL_ROLES,
    # Administration: managing what exists and who exists.
    "admin_devices": _ADMIN_ONLY,
    # A Technician's own operate-equipment surface (ADR-016): assigned
    # devices only, the shared device_manage_drawer(), never assignment or
    # registration. Deliberately its own route, not a role branch inside
    # "admin_devices" — see that ADR's "boundary by meaning, not location".
    "technician_devices": _TECHNICIAN_ONLY,
    # The technician workload roster + reassignment surface — a real route
    # replacing the sidebar's former routeless "Assignments" placeholder.
    # Admin-only, same as admin_devices: it reads/reassigns the whole fleet's
    # technician assignments, never a technician's own scope.
    "admin_assignments": _ADMIN_ONLY,
    "device_register": _ADMIN_ONLY,
    "admin_users": _ADMIN_ONLY,
    "audit_log": _ADMIN_ONLY,
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


class AuthorizationError(Exception):
    """An authenticated user reached for something they are not entitled to.

    Deliberately distinct from the ValueError raised for a bad identifier: the
    ROLE-1 decision that an authorization failure must never be folded into
    the same outcome as a nonexistent resource applies at the action layer as
    it does at the route layer.

    Defined here, in the pure module, so it can be caught without importing
    data access.
    """


#: Permissions where NO DEVICE IS INVOLVED. Not routes, and not device
#: actions: neither of the other two tables can express them.
#:
#: Two shapes qualify. Page content inside a page every role may open
#: (VIEW_ADMINISTRATION_OVERVIEW — the Administration block on /plants). And a
#: mutation whose target does not exist yet (REGISTER_DEVICE — the device is
#: what is being created, so there is no device_id to scope and no assignment
#: to resolve). What unites them is the absence of a device, which is exactly
#: what ACTION_POLICY requires; it is not a claim that they are the same kind
#: of thing.
VIEW_ADMINISTRATION_OVERVIEW = "view_administration_overview"
REGISTER_DEVICE = "register_device"
# AUTH-HARDEN-1: the Device Management table/drawers and the User
# Administration table/drawer are each one screen with no device to scope —
# same shape as REGISTER_DEVICE, mirroring ROUTE_POLICY's "admin_devices"/
# "admin_users" entries without being derived from them, for the reason
# REGISTER_DEVICE's own comment gives: a page that becomes reachable to more
# roles must not silently widen who may read or write its data.
MANAGE_DEVICES = "manage_devices"
# Mirrors ROUTE_POLICY["technician_devices"] the same way MANAGE_DEVICES
# mirrors ROUTE_POLICY["admin_devices"] — the route answers "may you open
# the page", this answers "may you pull the data", and the callback that
# builds the table re-checks this independently of page-context (P0-4,
# AUTH-HARDEN-1's own lesson: a forged page-context must not be trusted to
# gate a data read on its own).
VIEW_OWN_DEVICES = "view_own_devices"
MANAGE_USERS = "manage_users"
VIEW_AUDIT_LOG = "view_audit_log"
# ADR-013: device-less because a report spans zero, one or many devices —
# there is no single device_id to name. Grouped with the capabilities, not
# with the actions below, so the constant's position states its dimension.
EXPORT_DATA = "export_data"

PROGRAM_RTL = "program_rtl"
TOGGLE_MESSAGE_FORWARDING = "toggle_message_forwarding"
DEACTIVATE_RTL = "deactivate_rtl"
ACKNOWLEDGE_ALARM = "acknowledge_alarm"
MANAGE_ASSIGNMENT = "manage_assignment"
# THRESH-CONFIG-1 (C-01, framework only): setting/clearing the single
# global warning/critical temperature threshold. Device-less because there
# is exactly one global configuration, never a per-device one.
MANAGE_TEMPERATURE_THRESHOLD = "manage_temperature_threshold"
# VIB-CONFIG-1 (C-02, framework only): recording/editing/clearing a
# vibration contract question's answer. Device-less for the same reason
# as MANAGE_TEMPERATURE_THRESHOLD — this is contract METADATA, not a
# per-device reading.
MANAGE_VIBRATION_CONTRACT = "manage_vibration_contract"
# FRESHNESS-CONFIG-1: setting/clearing the global Stale-after threshold.
# Unlike the two above this one changes live monitoring state fleet-wide.
MANAGE_FRESHNESS_THRESHOLD = "manage_freshness_threshold"

#: capability -> roles. Role-only: no device is involved, so there is no
#: assignment condition to apply and no database read to make one.
#:
#: REGISTER_DEVICE mirrors ROUTE_POLICY["device_register"] and is asserted
#: equal to it in the tests. Deliberately NOT derived from it: the route
#: answers "may you open the page", this answers "may you perform the write",
#: and a page that becomes reachable to more roles must not silently widen
#: who may write.
CAPABILITY_POLICY: dict[str, frozenset[str]] = {
    VIEW_ADMINISTRATION_OVERVIEW: _ADMIN_ONLY,
    REGISTER_DEVICE: _ADMIN_ONLY,
    MANAGE_DEVICES: _ADMIN_ONLY,
    VIEW_OWN_DEVICES: _TECHNICIAN_ONLY,
    MANAGE_USERS: _ADMIN_ONLY,
    VIEW_AUDIT_LOG: _ADMIN_ONLY,
    # ADR-013, moved from ACTION_POLICY where it read
    # `(_EVERY_ROLE, _NO_ROLE)`. The empty assigned-only set was the tell:
    # no role's export permission ever depended on an assignment, so the
    # device dimension it was declared in did nothing. The SAME role set
    # carries over — this is a change of dimension, not of permission.
    EXPORT_DATA: _EVERY_ROLE,
    MANAGE_TEMPERATURE_THRESHOLD: _ADMIN_ONLY,
    MANAGE_VIBRATION_CONTRACT: _ADMIN_ONLY,
    MANAGE_FRESHNESS_THRESHOLD: _ADMIN_ONLY,
}

_NO_ROLE: frozenset[str] = frozenset()

#: action -> (roles allowed on any device, roles allowed only on assigned
#: ones). Sources: BR003, BR004, BR005, BR012 via the Functional
#: Specification, absorbed from the retired services/prototype_access.py.
#:
#: THE SECOND SET IS NOT A WEAKER FIRST SET. A role listed there may act only
#: where an assignment currently exists, which is why the two are separate
#: sets rather than one set plus a boolean: MANAGE_ASSIGNMENT has an empty
#: second set on purpose, because assignment is what GRANTS technician
#: authority and a technician who could manage it could grant it to
#: themselves.
ACTION_POLICY: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    PROGRAM_RTL: (_ADMIN_ONLY, frozenset({TECHNICIAN})),
    TOGGLE_MESSAGE_FORWARDING: (_ADMIN_ONLY, frozenset({TECHNICIAN})),
    DEACTIVATE_RTL: (_ADMIN_ONLY, frozenset({TECHNICIAN})),
    ACKNOWLEDGE_ALARM: (_ADMIN_ONLY, frozenset({TECHNICIAN})),
    MANAGE_ASSIGNMENT: (_ADMIN_ONLY, _NO_ROLE),
}


def may_perform_capability(role, capability: str) -> bool:
    """Whether `role` may see the page content behind `capability`.

    Default-deny on an unknown capability, and roles are compared exactly —
    the same posture as `may_access_route`.
    """
    if not isinstance(role, str):
        return False
    return role in CAPABILITY_POLICY.get(capability, frozenset())


def may_perform_action(role, action: str, *, is_assigned: bool) -> bool:
    """Whether `role` may perform `action` on a device.

    `is_assigned` is keyword-only AND undefaulted: a positional bool at a
    policy boundary is a seam, and this one decides whether a technician may
    act. The retired prototype_access defaulted it to False — the safe
    direction, but a default all the same, and a caller that simply forgot
    the argument looked identical to one that meant "unassigned".

    This function answers the ROLE question only. Whether the assignment
    actually exists is a database fact the caller supplies; keeping that out
    of here is what lets this module stay pure and synchronously testable.
    """
    if not isinstance(role, str):
        return False
    any_device, assigned_only = ACTION_POLICY.get(action, (_NO_ROLE, _NO_ROLE))
    if role in any_device:
        return True
    return bool(is_assigned) and role in assigned_only
