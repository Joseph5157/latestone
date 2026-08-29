"""Phase 7 - Affected Locations card (presentation).

The service ranked and composed; this card renders. It must not re-sort,
re-derive, or drop rows on its own.
"""
from __future__ import annotations

from dataclasses import dataclass

from components.command_center.affected_locations import (
    affected_locations_card,
    bar_width_percent,
)
from tests.dash_tree import find_by_class, text_of


@dataclass(frozen=True)
class _Loc:
    plant_id: str
    plant_name: str
    affected_rtls: int
    stale_rtls: int
    no_data_rtls: int
    total_monitored_rtls: int
    affected_percent: float


@dataclass(frozen=True)
class _Snap:
    affected_locations: tuple
    has_affected_locations: bool = True


RANKED = (
    _Loc("p1", "KZN North", 18, 12, 6, 24, 75.0),
    _Loc("p2", "Durban", 12, 12, 0, 30, 40.0),
    _Loc("p3", "Pinetown", 8, 4, 4, 20, 40.0),
    _Loc("p4", "Richards Bay", 5, 5, 0, 25, 20.0),
    _Loc("p5", "Newcastle", 2, 1, 1, 20, 10.0),
)


class TestBarWidth:
    def test_the_worst_plant_fills_the_bar(self):
        assert bar_width_percent(18, 18) == 100.0

    def test_bars_are_relative_to_the_worst_plant_not_the_fleet(self):
        """Ranking is comparative: the eye should read 'twice as bad as the
        next one', which absolute-percent widths would flatten."""
        assert bar_width_percent(9, 18) == 50.0

    def test_zero_affected_has_no_bar(self):
        assert bar_width_percent(0, 18) == 0.0

    def test_no_division_by_zero_when_nothing_is_affected(self):
        assert bar_width_percent(0, 0) == 0.0


class TestRankedRendering:
    def test_renders_every_ranked_plant(self):
        text = text_of(affected_locations_card(_Snap(RANKED)))
        for location in RANKED:
            assert location.plant_name in text

    def test_preserves_the_service_order_without_re_sorting(self):
        """The service owns the ranking rule (count desc, then name asc).
        A component that sorted again would be a second, silently
        divergent definition of 'worst'."""
        text = text_of(affected_locations_card(_Snap(RANKED)))
        positions = [text.index(loc.plant_name) for loc in RANKED]
        assert positions == sorted(positions)

    def test_shows_the_affected_count_for_each_row(self):
        text = text_of(affected_locations_card(_Snap(RANKED)))
        for count in ("18", "12", "8", "5", "2"):
            assert count in text

    def test_each_row_carries_a_bar(self):
        card = affected_locations_card(_Snap(RANKED))
        assert len(find_by_class(card, "command-center__rank-bar-fill")) == len(RANKED)

    def test_composition_is_available_without_dominating_the_count(self):
        """Stale/No Data composition may be shown, but the affected total
        stays the dominant figure."""
        card = affected_locations_card(_Snap(RANKED))
        assert find_by_class(card, "command-center__rank-value")


class TestQuietWhenNothingIsAffected:
    def test_an_all_healthy_fleet_reads_calm_not_empty(self):
        calm = (_Loc("p1", "Alpha", 0, 0, 0, 10, 0.0),)
        text = text_of(
            affected_locations_card(_Snap(calm, has_affected_locations=False))
        )
        assert "No RTLs require attention" in text

    def test_a_scope_with_no_plants_says_so_distinctly(self):
        """Different from 'all healthy': one is a measured result, the
        other is the absence of anything to measure."""
        text = text_of(affected_locations_card(_Snap((), has_affected_locations=False)))
        assert "No monitored RTLs" in text

    def test_zero_affected_plants_are_not_listed_among_the_ranked(self):
        """The service keeps them so the component can choose; the choice
        is to hide a calm plant from an exception-first ranking rather than
        pad the list with rows carrying no bar."""
        mixed = (
            _Loc("p1", "Busy", 4, 4, 0, 10, 40.0),
            _Loc("p2", "Calm", 0, 0, 0, 10, 0.0),
        )
        text = text_of(affected_locations_card(_Snap(mixed)))
        assert "Busy" in text
        assert "Calm" not in text
