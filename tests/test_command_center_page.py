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

    def test_situation_summary_is_a_live_region_not_a_placeholder(self):
        """Phase 5: this slot no longer names itself in the layout — it is an
        empty container the callback fills with four real cards, so its title
        text arrives with its content rather than being baked into the shell."""
        assert find_by_id(layout(), "command-center-situation-summary") is not None

    def test_the_remaining_panels_are_still_named_placeholders(self):
        """Phases 6-10 (docs/context/CC1_ROADMAP.md). The shell names every
        slot still to come, so nothing is silently missing when content lands."""
        text = text_of(layout())
        for panel_title in [
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
