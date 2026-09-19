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
        assert active_nav_key("/plants") == "overview"
