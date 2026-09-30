"""CC-NEW-1 / SWITCH-OVER-1 routing: Command Center route and role-aware landing."""
from __future__ import annotations

import pytest

from callbacks.navigation import active_nav_key
from callbacks.routing import landing_route_name
from routes import COMMAND_CENTER_PATH, parse_pathname
from services.authorization import (
    ADMINISTRATOR, GENERAL, ROUTE_POLICY, TECHNICIAN, may_access_route,
)


def test_command_center_path_and_removed_paths():
    assert COMMAND_CENTER_PATH == "/command-center"
    assert parse_pathname("/command-center").name == "command_center"
    for gone in ("/command-center-new", "/command-center/locations", "/command-center/x"):
        assert parse_pathname(gone).name == "unknown"


def test_policy_is_operational_roles_only():
    assert may_access_route(ADMINISTRATOR, "command_center")
    assert may_access_route(TECHNICIAN, "command_center")
    assert not may_access_route(GENERAL, "command_center")
    for gone in ("command_center_new", "command_center_locations", "overview_new"):
        assert gone not in ROUTE_POLICY


class TestLanding:
    @pytest.mark.parametrize("pathname", ["/", "", None])
    @pytest.mark.parametrize("role", [ADMINISTRATOR, TECHNICIAN])
    def test_root_lands_operational_roles_on_command_center(self, pathname, role):
        assert landing_route_name("overview", pathname, role) == "command_center"

    def test_root_lands_general_user_on_fleet_overview(self):
        assert landing_route_name("overview", "/", GENERAL) == "overview"

    @pytest.mark.parametrize("role", [ADMINISTRATOR, TECHNICIAN, GENERAL])
    def test_plants_is_always_fleet_overview(self, role):
        assert landing_route_name("overview", "/plants", role) == "overview"

    def test_signed_out_is_left_alone(self):
        assert landing_route_name("overview", "/", None) == "overview"

    def test_other_routes_are_untouched(self):
        assert landing_route_name("device", "/devices/x", ADMINISTRATOR) == "device"


class TestSidebarHighlight:
    def test_root_highlights_command_center_for_operational_roles(self):
        assert active_nav_key("/", ADMINISTRATOR) == "command_center"

    def test_root_highlights_overview_for_general(self):
        assert active_nav_key("/", GENERAL) == "overview"

    def test_command_center_path_highlights_command_center(self):
        assert active_nav_key("/command-center") == "command_center"

    def test_existing_behaviour_without_role(self):
        # RTL-LIST-ROUTE-01: the canonical list address; `/plants` renders
        # nothing and so highlights nothing.
        assert active_nav_key("/rtls") == "overview"


class TestSigningInAtTheLoginPath:
    """`/login` is not a route, so `parse_pathname` hands the router
    `unknown` for it. Signed out that is harmless — the router substitutes
    the login form for every path when nobody is signed in. But the moment
    the operator signs in AT `/login`, the pathname never changes, so the
    URL-driven redirect in `callbacks.auth` cannot fire: only `auth-store`
    changed. The router re-renders, resolves `unknown`, and falls through
    to the not-found panel — on the app's single most-typed address.

    Resolving it here rather than with a second redirect callback: this
    function's whole job is already "which route does this path render for
    this role", and the two are different events, not one bug fixed twice.
    """

    @pytest.mark.parametrize("role", [ADMINISTRATOR, TECHNICIAN])
    def test_operational_roles_land_on_command_center(self, role):
        assert landing_route_name("unknown", "/login", role) == "command_center"

    def test_general_user_lands_on_fleet_overview(self):
        """Not `unknown`: a General User has no Command Center, but they do
        have somewhere to land, and falling through would show them the
        not-found panel for signing in successfully."""
        assert landing_route_name("unknown", "/login", GENERAL) == "overview"

    def test_a_signed_out_visitor_is_left_alone(self):
        """Still `unknown` — and that is correct. The router never reaches
        the dispatch chain for a signed-out visitor; it returns the login
        form first."""
        assert landing_route_name("unknown", "/login", None) == "unknown"

    def test_deep_links_are_still_untouched(self):
        """Only the literal `/login` resolves to a landing page. A deep link
        must survive signing in, which is why the router substitutes the
        form for the requested path rather than redirecting to `/login`."""
        for role in (ADMINISTRATOR, TECHNICIAN, GENERAL):
            assert landing_route_name("plant", "/plants/3", role) == "plant"
