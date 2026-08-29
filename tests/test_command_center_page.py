"""Tests for the Command Center page layout (Phase 3+4: foundation and
shell). Layout only, no queries - matches pages/report_center.py's own
convention. Data is populated post-mount by callbacks/command_center.py.
"""
from __future__ import annotations

from pages.command_center import layout
from tests.dash_tree import find_by_id, text_of


class TestCommandCenterLayout:
    def test_layout_returns_a_component(self):
        assert hasattr(layout(), "children")

    def test_has_the_page_title(self):
        assert "Command Center" in text_of(layout())

    def test_has_a_scope_indicator_container_for_the_callback_to_fill(self):
        assert find_by_id(layout(), "command-center-scope-indicator") is not None

    def test_has_an_error_container_for_the_callback_to_fill(self):
        assert find_by_id(layout(), "command-center-error") is not None

    def test_all_six_roadmap_panels_are_present(self):
        """Phase 4's named panel slots (docs/context/CC1_ROADMAP.md). Content
        is Phase 5+; the shell must name every slot now so nothing is
        silently missing when content lands."""
        text = text_of(layout())
        for panel_title in [
            "Situation Summary",
            "Exception Intelligence",
            "Recent Operational Events",
            "Affected Locations",
            "Selected Location",
            "Priority Investigation",
        ]:
            assert panel_title in text

    def test_panels_do_not_claim_no_data_or_unavailable(self):
        """These panels are not built yet - a different fact from evaluated
        No Data (ADR-002) or Unavailable (ADR-001) states. Conflating them
        would misrepresent real data-availability semantics as a build gap."""
        text = text_of(layout()).lower()
        assert "no data" not in text
        assert "unavailable" not in text
