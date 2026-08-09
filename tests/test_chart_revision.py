"""Chart zoom must survive a refresh but reset when the view changes.

Regression tests for audit finding NEW-10.

`uirevision` was only `metric.key`. Plotly preserves the user's zoom/pan for as
long as that value is unchanged, so zooming into a few hours on Temperature/24h
and then switching to Temperature/30d kept the old x-axis window: the chart
looked like it was still showing a narrow slice, now of a 30-day dataset.

The revision has to be stable across the periodic refresh of the same view and
different for any view the operator can switch to.
"""
from __future__ import annotations

from components.metric_chart import build_metric_figure, chart_revision
from config.metrics import get_metric


class TestRevisionIdentity:
    def test_same_view_keeps_one_revision(self):
        """The refresh interval must not reset the operator's zoom."""
        a = chart_revision("temperature", "24h", None, None)
        b = chart_revision("temperature", "24h", None, None)
        assert a == b

    def test_period_change_changes_the_revision(self):
        assert chart_revision("temperature", "24h", None, None) != chart_revision(
            "temperature", "30d", None, None
        )

    def test_metric_change_changes_the_revision(self):
        assert chart_revision("temperature", "24h", None, None) != chart_revision(
            "voltage", "24h", None, None
        )

    def test_custom_bounds_change_the_revision(self):
        a = chart_revision("temperature", "custom", "2026-08-01", "2026-08-03")
        b = chart_revision("temperature", "custom", "2026-08-04", "2026-08-06")
        assert a != b

    def test_same_custom_bounds_keep_one_revision(self):
        a = chart_revision("temperature", "custom", "2026-08-01", "2026-08-03")
        b = chart_revision("temperature", "custom", "2026-08-01", "2026-08-03")
        assert a == b

    def test_every_period_is_distinct(self):
        revisions = {
            chart_revision("temperature", p, None, None)
            for p in ("24h", "7d", "30d", "custom")
        }
        assert len(revisions) == 4


class TestFigureUsesTheRevision:
    def test_figure_carries_the_supplied_revision(self):
        rev = chart_revision("temperature", "7d", None, None)
        fig = build_metric_figure(get_metric("temperature"), [], view_revision=rev)
        assert fig.layout.uirevision == rev

    def test_figures_for_different_periods_differ(self):
        metric = get_metric("temperature")
        a = build_metric_figure(
            metric, [], view_revision=chart_revision("temperature", "24h", None, None)
        )
        b = build_metric_figure(
            metric, [], view_revision=chart_revision("temperature", "30d", None, None)
        )
        assert a.layout.uirevision != b.layout.uirevision

    def test_falls_back_to_the_metric_key_when_no_revision_given(self):
        """Keeps existing callers working rather than silently disabling zoom."""
        fig = build_metric_figure(get_metric("temperature"), [])
        assert fig.layout.uirevision == "temperature"
