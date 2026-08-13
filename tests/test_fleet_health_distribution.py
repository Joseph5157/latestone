"""Fleet Data Health Distribution — a compact segmented bar restating the
Data Health KPI card's own counts. Supporting information, never a second
computation: these tests are mostly about the bar not being able to claim
something the counts do not support.
"""
from __future__ import annotations

from components.fleet_summary import fleet_health_distribution
from services.monitoring_service import Freshness
from tests.dash_tree import find_by_exact_class, text_of

F, S, N = Freshness.FRESH, Freshness.STALE, Freshness.NO_DATA


def _widths(block) -> dict[str, float]:
    """{state_class_suffix: width_percent} for every rendered segment."""
    widths = {}
    for seg in find_by_exact_class(block, "health-distribution__segment"):
        suffix = next(
            c.removeprefix("health-distribution__segment--")
            for c in seg.className.split()
            if c.startswith("health-distribution__segment--")
        )
        widths[suffix] = float(seg.style["width"].rstrip("%"))
    return widths


class TestSegmentProportions:
    def test_all_fresh_is_one_full_width_segment(self):
        block = fleet_health_distribution({F: 120, S: 0, N: 0})
        widths = _widths(block)
        assert widths == {"fresh": 100.0}

    def test_all_stale_is_one_full_width_segment(self):
        """The seeded-data case: every device stale, nothing fresh."""
        block = fleet_health_distribution({F: 0, S: 120, N: 0})
        widths = _widths(block)
        assert widths == {"stale": 100.0}

    def test_all_no_data_is_one_full_width_segment(self):
        block = fleet_health_distribution({F: 0, S: 0, N: 120})
        widths = _widths(block)
        assert widths == {"no_data": 100.0}

    def test_mixed_counts_produce_proportional_widths(self):
        block = fleet_health_distribution({F: 90, S: 27, N: 3})
        widths = _widths(block)
        assert widths["fresh"] == 75.0
        assert widths["stale"] == 22.5
        assert widths["no_data"] == 2.5
        assert sum(widths.values()) == 100.0

    def test_a_zero_count_state_renders_no_segment_at_all(self):
        """Zero width, not a fake minimum-visible sliver — no segment element
        for a state with no devices in it."""
        block = fleet_health_distribution({F: 100, S: 20, N: 0})
        widths = _widths(block)
        assert "no_data" not in widths
        assert len(find_by_exact_class(block, "health-distribution__segment")) == 2


class TestZeroTotal:
    def test_total_zero_does_not_raise(self):
        fleet_health_distribution({F: 0, S: 0, N: 0})  # must not raise / divide by zero

    def test_total_zero_renders_an_intentional_empty_state_not_a_fake_bar(self):
        block = fleet_health_distribution({F: 0, S: 0, N: 0})
        assert find_by_exact_class(block, "health-distribution__segment") == []
        assert "No active devices" in text_of(block)

    def test_total_zero_does_not_render_a_full_width_no_data_bar(self):
        """A 100%-width No Data segment would assert evidence (a device
        reporting nothing) that does not exist for an empty population."""
        block = fleet_health_distribution({F: 0, S: 0, N: 0})
        assert _widths(block) == {}


class TestLegend:
    def test_legend_always_lists_all_three_states(self):
        block = fleet_health_distribution({F: 0, S: 120, N: 0})
        labels = [
            text_of(el) for el in find_by_exact_class(block, "health-distribution__legend-label")
        ]
        assert labels == ["Fresh", "Stale", "No data"]

    def test_legend_shows_the_supplied_counts_including_zero(self):
        block = fleet_health_distribution({F: 0, S: 120, N: 0})
        counts = [
            text_of(el) for el in find_by_exact_class(block, "health-distribution__legend-count")
        ]
        assert counts == ["0", "120", "0"]

    def test_legend_renders_even_when_total_is_zero(self):
        """The empty-bar state above the legend must not swallow the legend
        row - all three states stay nameable even with nothing to show."""
        block = fleet_health_distribution({F: 0, S: 0, N: 0})
        labels = [
            text_of(el) for el in find_by_exact_class(block, "health-distribution__legend-label")
        ]
        assert labels == ["Fresh", "Stale", "No data"]

    def test_legend_labels_reuse_the_shared_freshness_presentation(self):
        """Not a second label set - the same source freshness_badge reads."""
        from components.freshness_presentation import FRESHNESS_PRESENTATION

        block = fleet_health_distribution({F: 1, S: 1, N: 1})
        labels = [
            text_of(el) for el in find_by_exact_class(block, "health-distribution__legend-label")
        ]
        assert labels == [FRESHNESS_PRESENTATION[s].label for s in (F, S, N)]


class TestComponentUsesSuppliedCountsOnly:
    def test_component_does_not_import_repositories_or_services_decision_functions(self):
        """Belt-and-braces alongside the architecture guard: this file's
        function signature takes counts in, nothing else."""
        import inspect

        params = inspect.signature(fleet_health_distribution).parameters
        assert list(params) == ["counts"]

    def test_result_depends_only_on_the_counts_argument(self):
        """Same counts, called twice, must render identically - nothing
        hidden is read from module state or the clock."""
        first = fleet_health_distribution({F: 5, S: 3, N: 1})
        second = fleet_health_distribution({F: 5, S: 3, N: 1})
        assert repr(first) == repr(second)
