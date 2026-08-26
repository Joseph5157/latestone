"""Contracts for the shared Plotly presentation building blocks.

`chart_presentation.py` holds only what is genuinely identical across the
full Metric Trend chart (`metric_chart.py`) and the metric workspace cells
(`metric_workspace.py`) — template, gridline colour, no-data styling, and hover
formatting. These tests pin that shared contract and that both chart
families actually consume it, without pinning the things that are meant to
differ (margins, height, titles, uirevision).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from components.chart_presentation import (
    GRIDLINE_COLOR,
    MUTED_TEXT_COLOR,
    TEMPLATE,
    grid_axis,
    hover_template,
    no_data_annotation,
)
from components.metric_chart import build_delta_figure, build_metric_figure
from components.metric_workspace import cell_figure
from config.metrics import get_metric
from services.monitoring_service import (
    ConsumptionBar, DeltaResult, DeltaStatus, Freshness, MetricView,
    MonitoringCondition, Reading,
)

T0 = datetime(2026, 8, 9, tzinfo=timezone.utc)


class TestGridAxis:
    def test_default_axis_shows_gridlines_in_the_shared_colour(self):
        assert grid_axis() == {"showgrid": True, "gridcolor": GRIDLINE_COLOR}

    def test_overrides_are_added_without_disturbing_the_shared_keys(self):
        axis = grid_axis(nticks=3, title=None)
        assert axis["showgrid"] is True
        assert axis["gridcolor"] == GRIDLINE_COLOR
        assert axis["nticks"] == 3
        assert axis["title"] is None


class TestNoDataAnnotation:
    def test_default_size_and_shared_colour(self):
        ann = no_data_annotation("No data available for the selected period")
        assert ann["text"] == "No data available for the selected period"
        assert ann["showarrow"] is False
        assert ann["font"] == {"size": 14, "color": MUTED_TEXT_COLOR}

    def test_size_is_caller_supplied_text_and_colour_stay_shared(self):
        """Quick Trend cells use a smaller size and different text, but the
        same muted colour — never the warning palette."""
        ann = no_data_annotation("No readings in this period", size=11)
        assert ann["font"]["size"] == 11
        assert ann["font"]["color"] == MUTED_TEXT_COLOR


class TestHoverTemplate:
    def test_states_utc_precision_and_unit(self):
        template = hover_template(get_metric("voltage"))
        assert "UTC" in template
        assert "%{y:.2f} kV" in template

    def test_respects_each_metrics_own_precision(self):
        assert "%{y:.1f} °C" in hover_template(get_metric("temperature"))
        assert "%{y:.3f} " in hover_template(get_metric("power_factor"))


class TestSharedContractIsActuallyConsumed:
    """The point of centralising these values: every chart family reads the
    same template/colour, not a copy that can drift."""

    def _bars(self):
        return [
            ConsumptionBar(T0, T0 + timedelta(hours=1), DeltaResult(5.0, DeltaStatus.OK)),
        ]

    def _delta_view(self):
        return MetricView(
            metric=get_metric("energy"), current=100.0, minimum=None, maximum=None,
            average=None, period_change=5.0, period_change_status=DeltaStatus.OK,
            series=[Reading(T0, 100.0), Reading(T0 + timedelta(hours=1), 105.0)],
            last_updated=T0, freshness=Freshness.FRESH,
            condition=MonitoringCondition.UNKNOWN, has_data=True,
        )

    def test_every_family_resolves_to_the_shared_named_template(self):
        import plotly.io as pio

        expected = pio.templates[TEMPLATE]
        line_fig = build_metric_figure(get_metric("voltage"), [Reading(T0, 11.0)])
        delta_fig = build_delta_figure(get_metric("energy"), self._bars())
        cell_fig = cell_figure(self._delta_view(), self._bars())

        assert line_fig.layout.template == expected
        assert delta_fig.layout.template == expected
        assert cell_fig.layout.template == expected

    def test_line_and_delta_and_cell_charts_agree_on_hover_format(self):
        """The primary line chart's hover used to omit UTC while the delta
        chart and every Quick Trend cell stated it — one shared function
        closes that gap."""
        line_fig = build_metric_figure(get_metric("voltage"), [Reading(T0, 11.0)])
        delta_fig = build_delta_figure(get_metric("energy"), self._bars())
        cell_fig = cell_figure(self._delta_view(), self._bars())

        line_hover = line_fig.data[0].hovertemplate
        delta_hover = next(t for t in delta_fig.data if t.type == "bar").hovertemplate
        cell_hover = next(t for t in cell_fig.data if t.type == "bar").hovertemplate

        assert "UTC" in line_hover
        assert line_hover == hover_template(get_metric("voltage"))
        assert delta_hover == hover_template(get_metric("energy"))
        assert cell_hover == hover_template(get_metric("energy"))

    def test_gridlines_use_the_shared_colour_in_every_family(self):
        line_fig = build_metric_figure(get_metric("voltage"), [Reading(T0, 11.0)])
        delta_fig = build_delta_figure(get_metric("energy"), self._bars())
        cell_fig = cell_figure(self._delta_view(), self._bars())

        assert line_fig.layout.yaxis.gridcolor == GRIDLINE_COLOR
        assert delta_fig.layout.yaxis.gridcolor == GRIDLINE_COLOR
        assert cell_fig.layout.yaxis.gridcolor == GRIDLINE_COLOR

    def test_no_data_annotation_colour_agrees_between_families(self):
        empty_line = build_metric_figure(get_metric("voltage"), [])
        empty_cell = cell_figure(
            MetricView(
                metric=get_metric("voltage"), current=None, minimum=None,
                maximum=None, average=None, period_change=None,
                period_change_status=DeltaStatus.INSUFFICIENT_DATA, series=[],
                last_updated=None, freshness=Freshness.NO_DATA,
                condition=MonitoringCondition.UNKNOWN, has_data=False,
            ),
            [],
        )
        assert empty_line.layout.annotations[0].font.color == MUTED_TEXT_COLOR
        assert empty_cell.layout.annotations[0].font.color == MUTED_TEXT_COLOR

    def test_quick_trend_x_axis_still_deliberately_hides_gridlines(self):
        """The one axis chart_presentation.grid_axis is not applied to —
        preserved on purpose, not an oversight."""
        cell_fig = cell_figure(self._delta_view(), self._bars())
        assert cell_fig.layout.xaxis.showgrid is False
