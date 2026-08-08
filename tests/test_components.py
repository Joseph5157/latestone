"""Unit tests for presentation logic in components - no database, no browser."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config.metrics import get_metric
from components.kpi_card import kpi_row
from components.metric_chart import build_metric_figure
from components.readings_table import build_table_rows
from services.monitoring_service import (
    Freshness,
    MetricView,
    MonitoringCondition,
    Reading,
)

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def _view(metric_key: str, **overrides) -> MetricView:
    defaults = dict(
        metric=get_metric(metric_key),
        current=10.0,
        minimum=5.0,
        maximum=15.0,
        average=10.0,
        period_change=None,
        series=[Reading(NOW, 10.0)],
        last_updated=NOW,
        freshness=Freshness.FRESH,
        condition=MonitoringCondition.UNKNOWN,
        has_data=True,
    )
    defaults.update(overrides)
    return MetricView(**defaults)


def _labels(component) -> list[str]:
    """Collect KPI card labels from the rendered Dash component tree."""
    found = []
    def walk(node):
        children = getattr(node, "children", None)
        if isinstance(children, list):
            for c in children:
                walk(c)
        elif children is not None:
            walk(children)
        if getattr(node, "className", "") == "kpi-card__label":
            found.append(node.children)
    walk(component)
    return found


class TestKpiRow:
    def test_statistics_metric_shows_min_max_average(self):
        labels = _labels(kpi_row(_view("temperature")))
        assert labels == ["Current", "Minimum", "Maximum", "Average"]

    def test_delta_metric_shows_period_change_instead(self):
        view = _view("energy", minimum=None, maximum=None, average=None, period_change=142.0)
        labels = _labels(kpi_row(view))
        assert labels == ["Current", "Period Change"]
        assert "Average" not in labels

    def test_no_data_view_renders_em_dashes(self):
        view = _view(
            "temperature", current=None, minimum=None, maximum=None,
            average=None, series=[], last_updated=None,
            freshness=Freshness.NO_DATA, has_data=False,
        )
        rendered = str(kpi_row(view))
        assert "\u2014" in rendered


class TestBuildTableRows:
    def test_formats_values_with_metric_precision_and_unit(self):
        rows = build_table_rows(get_metric("voltage"), [Reading(NOW, 11.0246)])
        assert rows[0]["value"] == "11.02 kV"

    def test_power_factor_row_has_no_unit_suffix(self):
        rows = build_table_rows(get_metric("power_factor"), [Reading(NOW, 0.9723)])
        assert rows[0]["value"] == "0.972"

    def test_includes_formatted_timestamp(self):
        rows = build_table_rows(get_metric("voltage"), [Reading(NOW, 11.0)])
        assert rows[0]["timestamp"] == "2026-08-08 12:00"

    def test_empty_readings_produce_no_rows(self):
        assert build_table_rows(get_metric("voltage"), []) == []

    def test_rows_contain_no_status_column(self):
        """Status columns implied thresholds we do not have."""
        rows = build_table_rows(get_metric("voltage"), [Reading(NOW, 11.0)])
        assert "status" not in rows[0]


class TestBuildMetricFigure:
    def test_axis_title_comes_from_metric_config(self):
        fig = build_metric_figure(get_metric("voltage"), [Reading(NOW, 11.0)])
        assert fig.layout.yaxis.title.text == "Voltage (kV)"

    def test_dimensionless_metric_omits_parenthetical_unit(self):
        fig = build_metric_figure(get_metric("power_factor"), [Reading(NOW, 0.97)])
        assert fig.layout.yaxis.title.text == "Power Factor"

    def test_plots_one_trace_for_the_series(self):
        readings = [Reading(NOW - timedelta(minutes=30), 10.0), Reading(NOW, 11.0)]
        fig = build_metric_figure(get_metric("voltage"), readings)
        assert len(fig.data) == 1
        assert len(fig.data[0].x) == 2

    def test_empty_series_renders_annotation_and_no_trace(self):
        fig = build_metric_figure(get_metric("voltage"), [])
        assert len(fig.data) == 0
        assert len(fig.layout.annotations) == 1

    def test_no_threshold_line_is_drawn(self):
        """No client-confirmed thresholds exist, so no threshold line."""
        fig = build_metric_figure(get_metric("temperature"), [Reading(NOW, 31.4)])
        assert not fig.layout.shapes
