"""CC-NEW-1 routing: the new Command Center route and the role-aware landing."""
from __future__ import annotations

import pytest

from callbacks.navigation import active_nav_key
from callbacks.routing import landing_route_name
from routes import COMMAND_CENTER_NEW_PATH, parse_pathname
from services.authorization import (
    ADMINISTRATOR, GENERAL, ROUTE_POLICY, TECHNICIAN, may_access_route,
)


def test_new_path_parses_to_its_own_route():
    assert COMMAND_CENTER_NEW_PATH == "/command-center-new"
    assert parse_pathname("/command-center-new").name == "command_center_new"
    assert parse_pathname("/command-center-new/x").name == "unknown"


def test_policy_matches_the_old_command_center():
    assert ROUTE_POLICY["command_center_new"] == ROUTE_POLICY["command_center"]
    assert may_access_route(ADMINISTRATOR, "command_center_new")
    assert may_access_route(TECHNICIAN, "command_center_new")
    assert not may_access_route(GENERAL, "command_center_new")


class TestLanding:
    @pytest.mark.parametrize("pathname", ["/", "", None])
    @pytest.mark.parametrize("role", [ADMINISTRATOR, TECHNICIAN])
    def test_root_lands_operational_roles_on_command_center(self, pathname, role):
        assert landing_route_name("overview", pathname, role) == "command_center_new"

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

    def test_new_path_highlights_command_center(self):
        assert active_nav_key("/command-center-new") == "command_center"

    def test_existing_behaviour_without_role(self):
        assert active_nav_key("/plants") == "overview"
