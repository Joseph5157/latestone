"""Tiles answer "is this rising or falling?", which a bare number cannot."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from components.metric_snapshot_strip import direction_text, metric_snapshot_strip
from config.metrics import get_metric
from services.monitoring_service import (
    DeltaResult, DeltaStatus, Freshness, MetricView, MonitoringCondition, Reading,
    _build_metric_view,
)
from tests.dash_tree import find_by_class, text_of

T0 = datetime(2026, 8, 9, tzinfo=timezone.utc)


def _view(key, change: DeltaResult, series=()):
    return MetricView(
        metric=get_metric(key), current=10.0, minimum=None, maximum=None, average=None,
        period_change=None, period_change_status=DeltaStatus.OK, series=list(series),
        last_updated=T0, freshness=Freshness.FRESH,
        condition=MonitoringCondition.UNKNOWN, has_data=True, change=change,
    )


class TestDirectionText:
    def test_a_rise_is_marked_up(self):
        text = direction_text(get_metric("voltage"), DeltaResult(0.31, DeltaStatus.OK))
        assert text.startswith("▲")

    def test_a_fall_is_marked_down(self):
        text = direction_text(get_metric("voltage"), DeltaResult(-0.31, DeltaStatus.OK))
        assert text.startswith("▼")

    def test_no_change_is_neither(self):
        text = direction_text(get_metric("voltage"), DeltaResult(0.0, DeltaStatus.OK))
        assert not text.startswith("▲")
        assert not text.startswith("▼")

    def test_unknown_change_shows_a_dash(self):
        assert direction_text(
            get_metric("energy"), DeltaResult(None, DeltaStatus.DISCONTINUITY)
        ) == "—"

    def test_insufficient_data_shows_a_dash_too(self):
        assert direction_text(
            get_metric("voltage"), DeltaResult(None, DeltaStatus.INSUFFICIENT_DATA)
        ) == "—"

    def test_value_carries_the_unit(self):
        text = direction_text(get_metric("voltage"), DeltaResult(0.31, DeltaStatus.OK))
        assert "kV" in text

    def test_a_fall_is_not_rendered_with_two_minus_signs(self):
        """The arrow carries the direction; the number must not repeat it."""
        text = direction_text(get_metric("voltage"), DeltaResult(-0.31, DeltaStatus.OK))
        assert text.count("-") + text.count("−") <= 1


class TestStripRendersDirection:
    def test_every_tile_shows_a_direction_line(self):
        views = [_view(k, DeltaResult(1.0, DeltaStatus.OK))
                 for k in ("temperature", "voltage")]
        strip = metric_snapshot_strip(views, "voltage", "dev-1")
        assert len(find_by_class(strip, "snapshot-tile__direction")) == 2

    def test_energy_never_shows_a_negative_direction(self):
        view = _view("energy", DeltaResult(None, DeltaStatus.DISCONTINUITY))
        strip = metric_snapshot_strip([view], "energy", "dev-1")
        text = text_of(find_by_class(strip, "snapshot-tile__direction")[0])
        assert "-" not in text

    def test_the_line_is_always_present_so_tiles_keep_one_height(self):
        """An absent line would make tiles step, and the strip feeds the
        §6.8 chart-top budget."""
        view = _view("voltage", DeltaResult(None, DeltaStatus.INSUFFICIENT_DATA))
        strip = metric_snapshot_strip([view], "voltage", "dev-1")
        assert find_by_class(strip, "snapshot-tile__direction")


class TestServiceAlwaysPopulatesChange:
    """`change` has a safe default so test factories need not restate it. This
    guards production against ever relying on that default."""

    def test_statistics_metric_gets_a_computed_change(self):
        series = [Reading(T0, 10.0), Reading(T0 + timedelta(minutes=30), 12.5)]
        view = _build_metric_view(get_metric("voltage"), None, series, T0)
        assert view.change == DeltaResult(2.5, DeltaStatus.OK)

    def test_cumulative_metric_reuses_the_period_delta_rules(self):
        series = [Reading(T0, 100.0), Reading(T0 + timedelta(minutes=30), 5.0)]
        view = _build_metric_view(get_metric("energy"), None, series, T0)
        assert view.change.status is DeltaStatus.DISCONTINUITY

    def test_single_reading_yields_insufficient_data(self):
        view = _build_metric_view(get_metric("voltage"), None, [Reading(T0, 10.0)], T0)
        assert view.change.status is DeltaStatus.INSUFFICIENT_DATA


class TestDirectionLineCannotGrowTheTile:
    """DEF-2 of this slice, found in the acceptance pass.

    The direction line had no CSS rule at all, so it inherited
    `white-space: normal`. On a 7-day energy delta the value read
    "* +428.0 MWh", wrapped to two lines, and because the strip is a grid that
    one wrapped tile stretched all eight from 97 px to 117 px and pushed the
    primary chart from 410 px to 430 px - past the section 6.8 budget of 420.

    It appeared only at some periods, which is why the Task 7 check at the
    default 24h missed it. Computed heights were re-verified across 24h, 7d and
    30d after the fix; these are the source guards.
    """

    import pathlib as _pathlib
    import re as _re

    CSS_TEXT = (
        _pathlib.Path(__file__).resolve().parent.parent / "assets" / "app.css"
    ).read_text(encoding="utf-8")

    def _block(self):
        match = self._re.search(
            r"\.snapshot-tile__direction\s*\{([^}]*)\}", self.CSS_TEXT, self._re.S
        )
        assert match, "the direction line must carry an explicit rule"
        return match.group(1)

    def test_the_line_never_wraps(self):
        assert "white-space: nowrap" in self._block()

    def test_the_line_has_a_fixed_height(self):
        """A value-dependent height makes the chart-top budget value-dependent."""
        block = self._block()
        assert self._re.search(r"\bheight:\s*\d+px", block)

    def test_overflow_is_revealed_not_clipped_silently(self):
        assert "text-overflow: ellipsis" in self._block()
