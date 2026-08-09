"""The device page fetches once and renders everything from that fetch."""
from __future__ import annotations

from datetime import datetime, timezone

from components.kpi_card import kpi_row
from components.metric_snapshot_strip import metric_snapshot_strip
from config.metrics import get_metric
from services.monitoring_service import (
    DeltaStatus, Freshness, MetricView, MonitoringCondition, Reading,
)
from tests.dash_tree import find_by_class, text_of

NOW = datetime(2026, 8, 9, 5, 43, tzinfo=timezone.utc)


def _view(metric_key="energy", period_change=None,
          status=DeltaStatus.OK, current=278.2, series=()):
    return MetricView(
        metric=get_metric(metric_key), current=current, minimum=None, maximum=None,
        average=None, period_change=period_change, period_change_status=status,
        series=list(series), last_updated=NOW, freshness=Freshness.FRESH,
        condition=MonitoringCondition.UNKNOWN, has_data=True,
    )


class TestPeriodChangeKpi:
    def test_a_known_delta_shows_the_number(self):
        row = kpi_row(_view(period_change=68.6, status=DeltaStatus.OK))
        values = [text_of(e) for e in find_by_class(row, "kpi-card__value")]
        assert "68.6" in values[1]

    def test_a_discontinuity_shows_a_dash_not_a_negative(self):
        row = kpi_row(_view(status=DeltaStatus.DISCONTINUITY))
        values = [text_of(e) for e in find_by_class(row, "kpi-card__value")]
        assert values[1].strip() == "—"

    def test_a_discontinuity_explains_itself(self):
        row = kpi_row(_view(status=DeltaStatus.DISCONTINUITY))
        secondary = [text_of(e) for e in find_by_class(row, "kpi-card__secondary")]
        assert "meter" in secondary[1].lower()

    def test_insufficient_data_does_not_claim_a_discontinuity(self):
        """Two different unknowns must not share one explanation."""
        row = kpi_row(_view(status=DeltaStatus.INSUFFICIENT_DATA))
        secondary = [text_of(e) for e in find_by_class(row, "kpi-card__secondary")]
        assert "discontinuity" not in secondary[1].lower()
        assert "readings" in secondary[1].lower()

    def test_the_current_meter_reading_survives_a_discontinuity(self):
        """The meter still reads what it reads; only the delta is unknown."""
        row = kpi_row(_view(status=DeltaStatus.DISCONTINUITY, current=278.2))
        values = [text_of(e) for e in find_by_class(row, "kpi-card__value")]
        assert "278.2" in values[0]


class TestStripAcceptsViews:
    """The strip is fed from the same MetricViews as everything else, so the
    page cannot show one number in the tile and another in the KPI."""

    def test_renders_a_tile_per_view(self):
        views = [_view("temperature"), _view("voltage")]
        strip = metric_snapshot_strip(views, "voltage", "dev-1")
        assert len(find_by_class(strip, "snapshot-tile__value")) == 2

    def test_marks_the_active_metric(self):
        views = [_view("temperature"), _view("voltage")]
        strip = metric_snapshot_strip(views, "voltage", "dev-1")
        active = [
            e for e in find_by_class(strip, "snapshot-tile")
            if "snapshot-tile--active" in e.className
        ]
        assert len(active) == 1

    def test_tile_link_preserves_the_period(self):
        from tests.dash_tree import links
        views = [_view("temperature")]
        strip = metric_snapshot_strip(views, "voltage", "dev-1", period="7d")
        assert all("period=7d" in href for _label, href in links(strip))
