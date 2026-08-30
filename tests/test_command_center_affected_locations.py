"""Phase 7 - Affected Locations card (presentation).

The service ranked and composed; this card renders. It must not re-sort,
re-derive, or drop rows on its own.
"""
from __future__ import annotations

from dataclasses import dataclass

from components.command_center.affected_locations import (
    LOCATIONS_PATH,
    TOP_N,
    affected_locations_card,
    bar_width_percent,
    ranked_locations_list,
    visible_locations,
)
from tests.dash_tree import find_by_class, links as _links, text_of, walk

_find = find_by_class


def _texts(node):
    return [text_of(n) for n in walk(node)]


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


def _many(count):
    """`count` affected plants, already ranked worst-first."""
    return tuple(
        _Loc(f"p{i}", f"Plant {i:02d}", count - i, count - i, 0, 40, 10.0)
        for i in range(count)
    )


def _scroll_regions(card):
    return find_by_class(card, "command-center__ranking-scroll")


def _focusable(node):
    return [n for n in walk(node) if getattr(n, "tabIndex", None) is not None]


class TestTopNDisclosure:
    """The panel names the worst TOP_N plants; the full population stays one
    click away.

    This SUPERSEDES the Phase 7 decision that the panel should list all 30.
    That reasoning was sound about the danger — hiding affected plants behind
    a "+22 more" cap removes the concentration picture — and it is answered
    here by DISCLOSURE rather than truncation: the service still ranks every
    plant, the subtitle still counts them, and the full page still lists them.
    Thirty rows in a fixed-height cell meant comparing rank 3 against rank 27
    by scrolling a small pane, which is not comparing at all.
    """

    LONG = _many(TOP_N + 12)

    def test_only_the_top_n_are_named(self):
        card = affected_locations_card(_Snap(self.LONG))
        assert len(find_by_class(card, "command-center__rank-bar-fill")) == TOP_N

    def test_the_worst_plants_are_the_ones_kept(self):
        shown, _ = visible_locations(list(self.LONG), None)
        assert [row.plant_id for row in shown] == [
            row.plant_id for row in self.LONG[:TOP_N]
        ]

    def test_a_list_at_the_cap_is_untouched(self):
        exactly = _many(TOP_N)
        shown, retained = visible_locations(list(exactly), None)
        assert len(shown) == TOP_N
        assert retained is None

    def test_a_short_list_is_untouched(self):
        shown, retained = visible_locations(list(_many(3)), None)
        assert len(shown) == 3
        assert retained is None

    def test_the_footer_offers_the_full_population_with_its_size(self):
        """"Show all" without a number makes the operator click to find out
        how much they are not seeing."""
        text = text_of(affected_locations_card(_Snap(self.LONG)))
        assert f"Show all {len(self.LONG)} affected plants" in text

    def test_the_footer_does_not_promise_more_when_nothing_is_hidden(self):
        text = text_of(affected_locations_card(_Snap(_many(3))))
        assert "Show all" not in text

    def test_the_data_is_never_truncated_only_the_view(self):
        """The service's ranking still holds every plant — the cap is a
        presentation choice made here, and reversible here."""
        snap = _Snap(self.LONG)
        assert len(snap.affected_locations) == TOP_N + 12


class TestSelectedPlantStaysVisible:
    """A selection that vanishes reads as a bug. The operator chose it."""

    LONG = _many(TOP_N + 12)

    def _snap_selecting(self, plant_id):
        class _Sel:
            def __init__(self, pid):
                self.plant_id = pid

        snap = _Snap(self.LONG)
        object.__setattr__(snap, "selected_location", _Sel(plant_id))
        return snap

    def test_a_selection_below_the_cut_is_retained(self):
        below = self.LONG[TOP_N + 3]
        shown, retained = visible_locations(list(self.LONG), below.plant_id)
        assert retained is below
        assert shown[-1] is below
        assert len(shown) == TOP_N + 1

    def test_a_selection_inside_the_cut_adds_nothing(self):
        inside = self.LONG[2]
        shown, retained = visible_locations(list(self.LONG), inside.plant_id)
        assert retained is None
        assert len(shown) == TOP_N

    def test_a_retained_row_says_why_it_is_there(self):
        """It is present for a different reason than the eight above it, and
        would otherwise read as rank 9."""
        below = self.LONG[TOP_N + 3]
        card = affected_locations_card(self._snap_selecting(below.plant_id))
        text = text_of(card)
        assert below.plant_name in text
        assert "because it is selected" in text
        assert f"rank {TOP_N + 4} of {len(self.LONG)}" in text

    def test_an_unaffected_selection_retains_nothing(self):
        """This panel ranks exceptions. A calm plant has no row to keep."""
        shown, retained = visible_locations(list(self.LONG), "not-affected")
        assert retained is None
        assert len(shown) == TOP_N


class TestTheListIsAlwaysHeightBounded:
    """The scroll region is a HEIGHT bound, not a row-count decision.

    Inside the fixed cockpit its CSS flexes it to the cell, so the rows must
    live inside it even at eight — otherwise the panel overflows its grid
    area on a short viewport.
    """

    def test_rows_are_wrapped_in_the_scroll_region(self):
        assert _scroll_regions(affected_locations_card(_Snap(_many(3))))

    def test_the_region_is_keyboard_reachable(self):
        """A scrollable region that cannot take focus is unreachable by
        keyboard (WCAG 2.1.1)."""
        region = _scroll_regions(affected_locations_card(_Snap(RANKED)))[0]
        # The STRING "0", not int 0: Dash types this prop as a string and
        # logs an invalid-argument error for an int on every callback fire.
        assert region.tabIndex == "0"

    def test_the_region_is_named_for_assistive_tech(self):
        region = _scroll_regions(affected_locations_card(_Snap(RANKED)))[0]
        assert region.role == "region"
        assert region.__getattribute__("aria-label")

    def test_an_empty_state_adds_no_tab_stop(self):
        """A focus stop that scrolls nothing is noise in the tab order."""
        empty = _Snap((), has_affected_locations=False)
        assert not _focusable(affected_locations_card(empty))


class TestScaleIsKnownWithoutScrolling:
    def test_the_subtitle_states_how_many_plants_are_affected(self):
        """Otherwise the scale of the problem is only discoverable by
        scrolling to the bottom and counting."""
        snap = _Snap(_many(22) + (_Loc("calm", "Calm", 0, 0, 0, 10, 0.0),))
        assert "22 of 23 plants" in text_of(affected_locations_card(snap))

    def test_a_single_affected_plant_reads_naturally(self):
        snap = _Snap((_Loc("p1", "Solo", 4, 4, 0, 10, 40.0),))
        assert "1 of 1 plant affected" in text_of(affected_locations_card(snap))


class TestViewAllLink:
    """Phase 7a: the panel is bounded, so it needs a way to the full list."""

    def test_the_panel_links_to_the_full_view(self):
        hrefs = [href for _label, href in _links(affected_locations_card(_Snap(RANKED)))]
        assert LOCATIONS_PATH in hrefs

    def test_the_link_is_absent_when_there_is_nothing_to_see(self):
        """A 'View all' over an empty list promises content that is not
        there."""
        empty = _Snap((), has_affected_locations=False)
        hrefs = [href for _label, href in _links(affected_locations_card(empty))]
        assert LOCATIONS_PATH not in hrefs


class TestFullViewRendersEverything:
    LONG = _many(TOP_N + 12)

    def test_renders_every_affected_plant(self):
        listing = ranked_locations_list(list(self.LONG))
        assert len(_find(listing, "command-center__rank-bar-fill")) == len(self.LONG)

    def test_is_not_wrapped_in_a_scroll_region(self):
        """The whole point of the full view is an unbounded list — a height
        cap here would reproduce the constraint it exists to escape."""
        listing = ranked_locations_list(list(self.LONG))
        assert not _find(listing, "command-center__ranking-scroll")

    def test_panel_and_full_view_render_the_same_rows(self):
        """One row renderer, two surfaces. A second copy would let the panel
        and the page drift into disagreeing about the same plant.

        Asserted over the plants the panel SHOWS, not over all of them: the
        panel is now a Top-N view, and demanding every plant appear in it
        would be testing the old disclosure decision, not the shared
        renderer this test is actually about.
        """
        panel_names = _texts(affected_locations_card(_Snap(self.LONG)))
        full_names = _texts(ranked_locations_list(list(self.LONG)))
        shown, _ = visible_locations(list(self.LONG), None)

        for location in shown:
            assert any(location.plant_name in t for t in panel_names)
        # The full view keeps its whole point: every affected plant.
        for location in self.LONG:
            assert any(location.plant_name in t for t in full_names)

    def test_the_panel_shows_fewer_plants_than_the_full_view(self):
        """The reason the full view exists at all."""
        shown, _ = visible_locations(list(self.LONG), None)
        assert len(shown) < len(self.LONG)
