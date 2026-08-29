"""Tests for the Command Center page layout (Phase 3+4: foundation and
shell). Layout only, no queries - matches pages/report_center.py's own
convention. Data is populated post-mount by callbacks/command_center.py.
"""
from __future__ import annotations

from pages.command_center import layout
from tests.dash_tree import find_by_class, find_by_id, links, text_of


class TestCommandCenterLayout:
    def test_layout_returns_a_component(self):
        assert hasattr(layout(), "children")

    def test_has_the_page_title(self):
        assert "Command Center" in text_of(layout())

    def test_has_a_scope_indicator_container_for_the_callback_to_fill(self):
        assert find_by_id(layout(), "command-center-scope-indicator") is not None

    def test_has_an_error_container_for_the_callback_to_fill(self):
        assert find_by_id(layout(), "command-center-error") is not None

    def test_has_no_app_brand_header(self):
        """The cockpit drops the Eskom/Powerplant brand bar and breadcrumb:
        the sidebar already shows where you are, and in a fixed-height
        layout that strip is ~60px spent restating it."""
        text = text_of(layout())
        assert "Powerplant Dashboard" not in text
        assert not find_by_class(layout(), "app-header")

    def test_sign_out_comes_from_the_sidebar_not_this_page(self):
        """Logout used to live in app_header, which this page no longer
        renders. It is not gone — it moved to the globally-mounted sidebar,
        which is why this page needs no sign-out of its own. Asserted from
        both sides so neither a page-local duplicate nor a silent loss can
        pass."""
        from components.app_sidebar import app_sidebar

        assert "/logout" not in [href for _label, href in links(layout())]
        assert "/logout" in [href for _label, href in links(app_sidebar("command_center", "administrator"))]

    def test_situation_summary_is_a_live_region_not_a_placeholder(self):
        """Phase 5: this slot no longer names itself in the layout — it is an
        empty container the callback fills with four real cards, so its title
        text arrives with its content rather than being baked into the shell."""
        assert find_by_id(layout(), "command-center-situation-summary") is not None

    def test_electrical_conditions_is_a_live_region_not_a_placeholder(self):
        """Phase 6: the Exception Intelligence slot now holds the Electrical
        Conditions card. Its id is unchanged from Phase 4 — the shell's DOM
        contract stays stable while its contents graduate."""
        assert find_by_id(layout(), "command-center-exception-intelligence") is not None

    def test_affected_locations_is_a_live_region_not_a_placeholder(self):
        """Phase 7: the ranked plant bar view. Id unchanged from Phase 4."""
        assert find_by_id(layout(), "command-center-affected-locations") is not None

    def test_selected_location_is_a_live_region_not_a_placeholder(self):
        """Phase 8: transformer concentration for the selected plant."""
        assert find_by_id(layout(), "command-center-selected-location") is not None

    def test_the_remaining_panels_are_still_named_placeholders(self):
        """Phases 9-10 (docs/context/CC1_ROADMAP.md). The shell names every
        slot still to come, so nothing is silently missing when content lands."""
        text = text_of(layout())
        for panel_title in [
            "Recent Operational Events",
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
