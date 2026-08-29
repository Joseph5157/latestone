"""Phase 5 - Situation Summary cards.

Components render values the facade already decided; none of them inspects
FleetHealth or recomputes freshness (ADR-008, ACTIVE_GATE.md service rule).
So these tests feed a plain snapshot and assert on rendered output.
"""
from __future__ import annotations

from dataclasses import dataclass

from components.command_center.situation_summary import (
    communication_card,
    fleet_health_card,
    inventory_card,
    needs_attention_card,
    situation_summary_panels,
)
from tests.dash_tree import text_of


@dataclass(frozen=True)
class _Snap:
    """The only fields the cards are allowed to read."""

    monitored_device_count: int = 120
    fresh_rtls: int = 85
    stale_rtls: int = 17
    no_data_rtls: int = 18
    attention_rtls: int = 35
    attention_percent: float = 29.166
    no_data_percent: float = 15.0
    plant_count: int = 8
    transformer_count: int = 42
    no_data_affected_plants: int = 5

    @property
    def has_monitored_devices(self) -> bool:
        return self.monitored_device_count > 0


EMPTY_SNAP = _Snap(
    monitored_device_count=0, fresh_rtls=0, stale_rtls=0, no_data_rtls=0,
    attention_rtls=0, attention_percent=0.0, no_data_percent=0.0,
    plant_count=0, transformer_count=0, no_data_affected_plants=0,
)


class TestFleetHealth:
    def test_shows_the_freshness_composition(self):
        text = text_of(fleet_health_card(_Snap()))
        for label in ("Fresh", "Stale", "No Data"):
            assert label in text
        assert "85" in text and "17" in text and "18" in text

    def test_states_the_monitored_population(self):
        assert "120" in text_of(fleet_health_card(_Snap()))

    def test_uses_no_electrical_condition_vocabulary(self):
        """ADR-001: Critical/Warning name already-classified EVENT types.
        Freshness is a data-delivery signal and must never borrow them -
        nor invent a 'Healthy' rollup the domain does not define."""
        text = text_of(fleet_health_card(_Snap())).lower()
        for forbidden in ("critical", "warning", "healthy"):
            assert forbidden not in text


class TestNeedsAttention:
    def test_shows_affected_count_and_share(self):
        text = text_of(needs_attention_card(_Snap()))
        assert "35" in text
        assert "29.2%" in text

    def test_states_the_definition_exactly(self):
        """ADR-002 - the definition is the card's whole meaning, so it is
        printed rather than left for the reader to infer."""
        assert "Stale + No Data" in text_of(needs_attention_card(_Snap()))

    def test_empty_scope_shows_no_percentage(self):
        """0.0% of 0 reads as a measured healthy result. It is the absence
        of any measurement."""
        text = text_of(needs_attention_card(EMPTY_SNAP))
        assert "%" not in text


class TestCommunication:
    EXACT_COPY = "At least one monitored metric has no reading."

    def test_shows_no_data_count_and_share(self):
        text = text_of(communication_card(_Snap()))
        assert "18" in text
        assert "15.0%" in text

    def test_carries_the_exact_frozen_copy(self):
        assert self.EXACT_COPY in text_of(communication_card(_Snap()))

    def test_shows_affected_plant_count(self):
        assert "5" in text_of(communication_card(_Snap()))

    def test_has_no_age_buckets(self):
        """ADR-002: there is no per-metric missing-since fact to derive a
        duration from. device_last_updated describes a DIFFERENT metric."""
        text = text_of(communication_card(_Snap()))
        for bucket in (">24h", ">48h", ">72h", "24h", "48h", "72h"):
            assert bucket not in text

    def test_never_says_never_reported(self):
        """A NO_DATA RTL may have several metrics reporting fine."""
        assert "never reported" not in text_of(communication_card(_Snap())).lower()


class TestInventory:
    def test_shows_the_three_monitoring_levels(self):
        text = text_of(inventory_card(_Snap()))
        assert "8" in text and "Plants" in text
        assert "42" in text and "Transformers" in text
        assert "120" in text and "RTL Devices" in text

    def test_carries_the_frozen_population_subtitle(self):
        """Frozen by the user: not 'Total Assets', not 'Registered Assets' -
        the wording must name the same population driving Fleet Health and
        Needs Attention."""
        text = text_of(inventory_card(_Snap()))
        assert "Monitored assets in your current access scope" in text
        assert "Total Assets" not in text
        assert "Registered" not in text


class TestSituationSummaryPanels:
    def test_returns_the_four_cards_in_order(self):
        panels = situation_summary_panels(_Snap())
        assert len(panels) == 4
        text = " ".join(text_of(p) for p in panels)
        for title in ("Fleet Health", "Needs Attention", "Communication", "Inventory"):
            assert title in text
