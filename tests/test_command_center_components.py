"""Tests for the fresh Command Center presentation family (ADR-008).

No imports from fleet_condition.py/needs_attention.py - this family renders
its own markup over the same service-layer data those pages also read.
"""
from __future__ import annotations

from components.command_center.primitives import (
    cc_card,
    panel_not_yet_built,
    scope_indicator_text,
)
from tests.dash_tree import find_by_exact_class, text_of


class TestScopeIndicatorText:
    def test_singular_device(self):
        assert scope_indicator_text(1) == "Current access · 1 monitored RTL"

    def test_plural_devices(self):
        assert scope_indicator_text(120) == "Current access · 120 monitored RTLs"

    def test_zero_devices(self):
        """Zero is a real, distinct count - not the same as Unavailable
        (ADR-001). An empty scope is a legitimate state to say plainly."""
        assert scope_indicator_text(0) == "Current access · 0 monitored RTLs"


class TestCcCard:
    def test_wraps_children_with_the_command_center_namespace(self):
        card = cc_card("Fleet Health", [], subtitle="Operational picture")
        assert "command-center__card" in find_by_exact_class(card, "command-center__card")[0].className

    def test_title_and_subtitle_are_rendered(self):
        card = cc_card("Fleet Health", [], subtitle="Operational picture")
        text = text_of(card)
        assert "Fleet Health" in text
        assert "Operational picture" in text


class TestPanelNotYetBuilt:
    def test_names_the_panel_and_does_not_claim_no_data(self):
        panel = panel_not_yet_built("Situation Summary")
        text = text_of(panel)
        assert "Situation Summary" in text
        # Must never read as a data-availability claim (ADR-001/002's
        # Unavailable/No Data are specific, evaluated states - this is
        # "not built yet", a different fact, and must not be confusable
        # with either.
        assert "no data" not in text.lower()
        assert "unavailable" not in text.lower()
