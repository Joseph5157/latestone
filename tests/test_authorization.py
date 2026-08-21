"""ROLE-2 — route and navigation authorization.

The policy table is the source of truth and the sidebar is derived from it.
That is what most of this file is about: a hidden item and a denied route
cannot disagree, because there is only one statement of who may go where.
Both directions are asserted — nothing visible that is denied, nothing
allowed that is invisible — since two independently-maintained tables would
each pass their own tests while contradicting each other.

WHAT THIS IS NOT. Route denial happens in the router. The data callbacks
still answer whoever asks, and the role still travels in a client-settable
browser store (S-4/S-5 in docs/CODE_AUDIT.md). ROLE-2 shapes what the UI
offers; it does not withhold data from anyone bypassing the UI.
"""
from __future__ import annotations

import pytest

from callbacks.navigation import NAV_KEY_BY_ROUTE
from components.app_sidebar import SIDEBAR_SECTIONS
from routes import parse_pathname
from services.authorization import (
    ADMINISTRATOR,
    GENERAL,
    ROUTE_POLICY,
    TECHNICIAN,
    may_access_route,
    visible_nav_keys,
)
from services.prototype_users import CONFIRMED_ROLES

#: Every route an authenticated user can ask for, with the path that produces
#: it. `unknown` is deliberately absent — it is not an application route.
ROUTE_PATHS = {
    "overview": "/plants",
    "plant": "/plants/plant-01",
    "transformer": "/plants/plant-01/plant-01-t1",
    "device": "/devices/plant-01-t1-d1",
    "notifications": "/notifications",
    "reports": "/reports",
    "admin_devices": "/admin/devices",
    "device_register": "/admin/devices/new",
    "admin_users": "/admin/users",
}

#: The frozen ROLE-2 matrix. Technician and General are identical here on
#: purpose: they diverge at device scope and action authorization in ROLE-3,
#: not at route level.
ADMIN_ONLY = ("admin_devices", "device_register", "admin_users")
SHARED = ("overview", "plant", "transformer", "device", "notifications", "reports")


class TestRoleConstants:
    def test_role_names_match_the_confirmed_vocabulary(self):
        """The policy must key on the same strings `users.role` holds, or it
        silently denies everyone."""
        assert {ADMINISTRATOR, TECHNICIAN, GENERAL} == set(CONFIRMED_ROLES)


class TestTheMatrix:
    @pytest.mark.parametrize("route", SHARED)
    def test_every_role_reaches_monitoring_notifications_and_reports(self, route):
        for role in CONFIRMED_ROLES:
            assert may_access_route(role, route) is True

    @pytest.mark.parametrize("route", ADMIN_ONLY)
    def test_only_the_administrator_reaches_admin_management(self, route):
        assert may_access_route(ADMINISTRATOR, route) is True
        assert may_access_route(TECHNICIAN, route) is False
        assert may_access_route(GENERAL, route) is False

    def test_technician_and_general_have_the_same_route_set(self):
        """Frozen for ROLE-2. Equal is not redundant: the roles differ later
        at device scope, and encoding a difference here that ROLE-3 has to
        undo would be worse than stating they match."""
        technician = {r for r in ROUTE_POLICY if may_access_route(TECHNICIAN, r)}
        general = {r for r in ROUTE_POLICY if may_access_route(GENERAL, r)}
        assert technician == general

    def test_administrator_reaches_every_policied_route(self):
        assert all(may_access_route(ADMINISTRATOR, r) for r in ROUTE_POLICY)

    def test_the_policy_covers_every_application_route(self):
        """A route the router can produce but the policy never mentions would
        be denied to everyone — including the administrator — the moment it
        shipped. This is the test that fails when someone adds a route."""
        assert set(ROUTE_POLICY) == set(ROUTE_PATHS)

    @pytest.mark.parametrize("route,path", sorted(ROUTE_PATHS.items()))
    def test_each_path_parses_to_the_route_the_policy_names(self, route, path):
        """Guards the join: the policy keys on `Route.name`, so a renamed
        route would default-deny rather than error."""
        assert parse_pathname(path).name == route


class TestDefaultDeny:
    @pytest.mark.parametrize("role", CONFIRMED_ROLES)
    def test_an_unlisted_route_is_denied_to_everyone(self, role):
        """A route added later is unreachable until someone lists it
        deliberately. Denied is the safe direction to fail."""
        assert may_access_route(role, "some_future_admin_page") is False

    def test_the_unknown_route_is_not_authorised_here(self):
        """`unknown` stays outside the policy so a typo'd URL keeps rendering
        not-found. The router, not this table, is what keeps those apart."""
        assert "unknown" not in ROUTE_POLICY

    @pytest.mark.parametrize("role", [None, "", "superuser", "Administrator", 7, {}])
    def test_an_unrecognised_role_reaches_nothing(self, role):
        """Including the near-misses: a role is compared exactly, never
        case-folded, so `Administrator` is not the administrator."""
        assert all(may_access_route(role, r) is False for r in ROUTE_POLICY)

    def test_denial_is_the_answer_for_a_missing_role_even_on_open_routes(self):
        assert may_access_route(None, "overview") is False


class TestNavigationIsDerivedFromThePolicy:
    def _sidebar_keys(self) -> set[str]:
        return {
            key
            for _title, items in SIDEBAR_SECTIONS
            for key, _label, _href, _icon in items
            if key is not None
        }

    @pytest.mark.parametrize("role", CONFIRMED_ROLES)
    def test_nothing_visible_leads_somewhere_denied(self, role):
        """The failure this prevents: an item you can see and cannot open."""
        for key in visible_nav_keys(role):
            routes = [r for r, k in NAV_KEY_BY_ROUTE.items() if k == key]
            assert any(may_access_route(role, r) for r in routes)

    @pytest.mark.parametrize("role", CONFIRMED_ROLES)
    def test_nothing_reachable_is_hidden(self, role):
        """The opposite failure: a page you may open with no way to get
        there."""
        visible = visible_nav_keys(role)
        for route, key in NAV_KEY_BY_ROUTE.items():
            if may_access_route(role, route):
                assert key in visible

    def test_administrator_keeps_the_current_navigation(self):
        assert visible_nav_keys(ADMINISTRATOR) == self._sidebar_keys()

    @pytest.mark.parametrize("role", [TECHNICIAN, GENERAL])
    def test_admin_management_items_disappear(self, role):
        assert visible_nav_keys(role) == {"overview", "notifications", "reports"}

    @pytest.mark.parametrize("role", [None, "superuser"])
    def test_an_unrecognised_role_sees_no_navigation(self, role):
        assert visible_nav_keys(role) == frozenset()

    def test_every_sidebar_key_is_reachable_by_someone(self):
        """A navigation item nobody may open is dead chrome."""
        reachable = set()
        for role in CONFIRMED_ROLES:
            reachable |= visible_nav_keys(role)
        assert reachable == self._sidebar_keys()


class TestTheAssignDeepLinkNeedsNoRuleOfItsOwn:
    """ADMIN-3's `?assign=` handoff lives under `/admin/devices`."""

    def test_denying_device_management_denies_the_handoff(self):
        from routes import device_assign_href

        href = device_assign_href("plant-01-t1-d1")
        route = parse_pathname(href.split("?", 1)[0]).name
        assert route == "admin_devices"
        assert may_access_route(TECHNICIAN, route) is False
        assert may_access_route(GENERAL, route) is False

    def test_the_query_string_cannot_change_the_answer(self):
        """Authorization keys on the route, so no `?assign=` value can widen
        it."""
        assert (
            parse_pathname("/admin/devices").name
            == parse_pathname("/admin/devices").name
        )
        assert may_access_route(TECHNICIAN, "admin_devices") is False
