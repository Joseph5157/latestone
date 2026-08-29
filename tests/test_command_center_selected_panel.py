"""Phase 8 - Selected Location panel (presentation)."""
from __future__ import annotations

from dataclasses import dataclass

from components.command_center.selected_location import selected_location_card
from tests.dash_tree import find_by_class, links, text_of


@dataclass(frozen=True)
class _T:
    transformer_id: str
    transformer_code: str
    affected_rtls: int
    stale_rtls: int
    no_data_rtls: int
    total_monitored_rtls: int


@dataclass(frozen=True)
class _Loc:
    plant_id: str = "plant-01"
    plant_name: str = "KZN North"
    affected_rtls: int = 18
    stale_rtls: int = 12
    no_data_rtls: int = 6
    total_monitored_rtls: int = 24
    transformers: tuple = ()

    @property
    def has_monitored_rtls(self) -> bool:
        return self.total_monitored_rtls > 0


@dataclass(frozen=True)
class _Snap:
    selected_location: object = None


RANKED = (
    _T("plant-01-t4", "TRF-04", 5, 5, 0, 8),
    _T("plant-01-t7", "TRF-07", 3, 2, 1, 6),
    _T("plant-01-t11", "TRF-11", 2, 2, 0, 5),
)


class TestCalmFleet:
    """Nothing resolves only when nothing is affected anywhere — selection
    otherwise falls back to the worst plant. So this state is a calm fleet,
    not a missing choice."""

    def test_states_the_fleet_is_calm_rather_than_prompting(self):
        text = text_of(selected_location_card(_Snap()))
        assert "No RTLs currently require attention across the monitored fleet" in text

    def test_is_not_dressed_as_an_error_or_unavailable(self):
        text = text_of(selected_location_card(_Snap())).lower()
        assert "unavailable" not in text
        assert "error" not in text

    def test_shows_no_transformer_rows(self):
        assert not find_by_class(selected_location_card(_Snap()), "command-center__rank-row")


class TestSelected:
    SNAP = _Snap(_Loc(transformers=RANKED))

    def test_names_the_selected_plant_and_its_load(self):
        text = text_of(selected_location_card(self.SNAP))
        assert "KZN North" in text
        assert "18 of 24" in text

    def test_shows_the_stale_and_no_data_composition(self):
        """"18 affected" alone does not say whether the plant stopped
        reporting or never started."""
        text = text_of(selected_location_card(self.SNAP))
        assert "Stale" in text and "12" in text
        assert "No Data" in text and "6" in text

    def test_renders_every_transformer_in_service_order(self):
        card = selected_location_card(self.SNAP)
        text = text_of(card)
        positions = [text.index(t.transformer_code) for t in RANKED]
        assert positions == sorted(positions)
        assert len(find_by_class(card, "command-center__rank-bar-fill")) == len(RANKED)

    def test_each_transformer_deep_links_to_its_existing_route(self):
        """Flattens investigation without duplicating the hierarchy: the
        destination is the Transformer page that already exists."""
        hrefs = [href for _label, href in links(selected_location_card(self.SNAP))]
        assert "/plants/plant-01/plant-01-t4" in hrefs

    def test_offers_a_link_to_the_plant_itself(self):
        hrefs = [href for _label, href in links(selected_location_card(self.SNAP))]
        assert "/plants/plant-01" in hrefs

    def test_a_plant_with_no_affected_rtls_reads_as_measured_calm(self):
        calm = _Snap(_Loc(affected_rtls=0, stale_rtls=0, no_data_rtls=0, transformers=()))
        text = text_of(selected_location_card(calm))
        assert "No RTLs currently require attention in this Plant" in text
        assert "Unavailable" not in text

    def test_a_plant_with_nothing_monitored_is_a_distinct_state(self):
        """Different fact from "nothing is wrong here": there is nothing to
        be wrong. Reporting the former would invent a clean bill of health
        for a plant that reports nothing at all."""
        empty = _Snap(_Loc(
            affected_rtls=0, stale_rtls=0, no_data_rtls=0,
            total_monitored_rtls=0, transformers=(),
        ))
        text = text_of(selected_location_card(empty))
        assert "No monitored RTLs in this Plant" in text
        assert "require attention" not in text
