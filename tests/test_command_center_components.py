"""Tests for the fresh Command Center presentation family (ADR-008).

No imports from fleet_condition.py/needs_attention.py - this family renders
its own markup over the same service-layer data those pages also read.
"""
from __future__ import annotations

from components.command_center.primitives import (
    cc_card,
    panel_not_yet_built,
)
from tests.dash_tree import find_by_exact_class, text_of

# CC-HEADER-TRIM-1: `scope_indicator_text` and its three tests are gone. The
# count it formatted was `snapshot.total_rtls` — the same integer the Working
# severity card renders as its denominator, for every role (Technician
# included: `services/attention_service.py` scopes `total_rtls` already).


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
