"""Phase 7 - Affected Locations card (presentation).

The service ranked and composed; this card renders. It must not re-sort,
re-derive, or drop rows on its own.
"""
from __future__ import annotations

from dataclasses import dataclass

from components.command_center.affected_locations import (
    LOCATIONS_PATH,
    SCROLL_AFTER_ROWS,
    affected_locations_card,
    bar_width_percent,
    ranked_locations_list,
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


class TestLongListScrolls:
    """30 affected plants made the panel dominate the page. Bounding its
    HEIGHT is the fix; bounding the DATA is not - hiding affected plants
    behind a "+22 more" cap would remove exactly the concentration picture
    this panel exists to give."""

    LONG = _many(SCROLL_AFTER_ROWS + 12)

    def test_a_long_list_is_wrapped_in_a_scroll_region(self):
        assert _scroll_regions(affected_locations_card(_Snap(self.LONG)))

    def test_every_row_is_still_rendered_not_truncated(self):
        card = affected_locations_card(_Snap(self.LONG))
        assert len(find_by_class(card, "command-center__rank-bar-fill")) == len(self.LONG)

    def test_the_scroll_region_is_keyboard_reachable(self):
        """A scrollable region that cannot take focus is unreachable by
        keyboard (WCAG 2.1.1) - the content is visually present and
        functionally unavailable."""
        region = _scroll_regions(affected_locations_card(_Snap(self.LONG)))[0]
        # The STRING "0", not int 0: Dash types this prop as a string and
        # logs an invalid-argument error for an int on every callback fire.
        # Asserting the Python attribute alone let that through once.
        assert region.tabIndex == "0"

    def test_the_scroll_region_is_named_for_assistive_tech(self):
        """A focusable region with no accessible name announces as nothing."""
        region = _scroll_regions(affected_locations_card(_Snap(self.LONG)))[0]
        assert region.role == "region"
        assert region.__getattribute__("aria-label")


class TestShortListDoesNotScroll:
    SHORT = _many(3)

    def test_a_short_list_has_no_scroll_region(self):
        assert not _scroll_regions(affected_locations_card(_Snap(self.SHORT)))

    def test_a_short_list_adds_no_tab_stop(self):
        """A focus stop that scrolls nothing is noise in the tab order."""
        assert not _focusable(affected_locations_card(_Snap(self.SHORT)))

    def test_the_boundary_row_count_does_not_scroll(self):
        exactly = _many(SCROLL_AFTER_ROWS)
        assert not _scroll_regions(affected_locations_card(_Snap(exactly)))


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
    LONG = _many(SCROLL_AFTER_ROWS + 12)

    def test_renders_every_affected_plant(self):
        listing = ranked_locations_list(list(self.LONG))
        assert len(_find(listing, "command-center__rank-bar-fill")) == len(self.LONG)

    def test_is_not_wrapped_in_a_scroll_region(self):
        """The whole point of the full view is an unbounded list — a height
        cap here would reproduce the constraint it exists to escape."""
        listing = ranked_locations_list(list(self.LONG))
        assert not _find(listing, "command-center__ranking-scroll")

    def test_panel_and_full_view_render_the_same_rows(self):
        """One row renderer, two surfaces. A second copy would let the
        panel and the page drift into disagreeing about the same plant."""
        panel_names = [
            t for t in _texts(affected_locations_card(_Snap(self.LONG)))
        ]
        full_names = [t for t in _texts(ranked_locations_list(list(self.LONG)))]
        for location in self.LONG:
            assert any(location.plant_name in t for t in panel_names)
            assert any(location.plant_name in t for t in full_names)
