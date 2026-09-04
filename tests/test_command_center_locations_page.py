"""Tests for the Affected Locations page layout (pages/command_center_locations.py).

Layout only, no queries — matches pages/command_center.py's own convention.
"""
from __future__ import annotations

from pages.command_center_locations import layout
from tests.dash_tree import find_by_id


class TestCommandCenterLocationsLayout:
    def test_has_an_error_container_for_the_callback_to_fill(self):
        assert find_by_id(layout(), "command-center-locations-error") is not None

    def test_error_container_carries_the_shared_listing_error_class(self):
        error = find_by_id(layout(), "command-center-locations-error")
        assert error.className == "listing-error"
