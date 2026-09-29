"""The device page fetches once and renders everything from that fetch."""
from __future__ import annotations

from datetime import datetime, timezone

from components.kpi_card import kpi_row
from components.metric_workspace import metric_workspace
from config.metrics import get_metric
from services.monitoring_service import (
    DeltaStatus, Freshness, MetricView, MonitoringCondition, Reading,
)
from tests.dash_tree import find_by_class, find_by_exact_class, text_of

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


class TestWorkspaceAcceptsViews:
    """The workspace is fed from the same MetricViews as everything else, so
    the page cannot show one number in a cell and another in the KPI."""

    def test_renders_a_cell_per_view(self):
        from tests.dash_tree import find_by_exact_class

        views = {"temperature": _view("temperature"), "voltage": _view("voltage")}
        ws = metric_workspace(views, {}, "voltage", "dev-1")
        assert len(find_by_exact_class(ws, "metric-cell")) == 2

    def test_marks_the_active_metric(self):
        views = {
            m.key: _view(m.key) for m in (get_metric("temperature"), get_metric("voltage"))
        }
        ws = metric_workspace(views, {}, "voltage", "dev-1")
        selected = [
            e for e in find_by_exact_class(ws, "metric-cell")
            if "metric-cell--selected" in e.className
        ]
        assert len(selected) == 1

    def test_cell_link_preserves_the_period(self):
        from tests.dash_tree import links

        views = {"temperature": _view("temperature")}
        ws = metric_workspace(views, {}, "voltage", "dev-1", period="7d")
        assert all("period=7d" in href for _label, href in links(ws))


class TestBinLabel:
    def test_names_the_bin_width_in_operator_units(self):
        from datetime import timedelta

        from services.monitoring_service import bin_label

        assert bin_label(timedelta(minutes=30)) == "30 min bars"
        assert bin_label(timedelta(hours=6)) == "6 h bars"
        assert bin_label(timedelta(days=1)) == "1 d bars"
        assert bin_label(timedelta(days=7)) == "7 d bars"


class TestWindowAndPrimeReachTheView:
    """The chart bins over the same window the KPI totals, opened by the same
    priming reading. If the two used different bases the bars would stop
    summing to the KPI, which is the invariant the bar arithmetic exists to
    protect."""

    def test_a_delta_metric_carries_its_window_and_prime(self, monkeypatch):
        from datetime import timedelta

        from repositories import plant_monitoring_repository as repo
        from services import monitoring_service as svc

        window_start = NOW - timedelta(hours=24)
        prime = Reading(window_start, 900.0)
        series = [Reading(window_start + timedelta(minutes=30 * i), 1000.0 + i)
                  for i in range(4)]

        monkeypatch.setattr(svc, "_now", lambda: NOW)
        monkeypatch.setattr(
            svc.repo, "get_latest_readings_for_device",
            lambda device_id: {"energy": type("R", (), {
                "timestamp": series[-1].timestamp, "value": series[-1].value})()},
        )
        monkeypatch.setattr(
            svc.repo, "get_readings_for_device_in_range",
            lambda device_id, metrics, start, end: {"energy": series},
        )
        monkeypatch.setattr(
            svc.repo, "get_last_reading_before",
            lambda device_id, metric, ts: prime,
        )

        views = svc.get_device_full_view("dev-1", svc.Period.LAST_24H)
        energy = views["energy"]
        assert energy.prime == prime
        assert energy.window_start is not None and energy.window_end is not None

    def test_bars_sum_to_the_reported_period_change(self, monkeypatch):
        from datetime import timedelta

        from services import monitoring_service as svc

        window_start = NOW - timedelta(hours=4)
        prime = Reading(window_start, 900.0)
        series = [Reading(window_start + timedelta(minutes=30 * (i + 1)), 1000.0 + 2 * i)
                  for i in range(8)]

        monkeypatch.setattr(svc, "_now", lambda: NOW)
        monkeypatch.setattr(
            svc.repo, "get_latest_readings_for_device",
            lambda device_id: {"energy": type("R", (), {
                "timestamp": series[-1].timestamp, "value": series[-1].value})()},
        )
        monkeypatch.setattr(
            svc.repo, "get_readings_for_device_in_range",
            lambda device_id, metrics, start, end: {"energy": series},
        )
        monkeypatch.setattr(
            svc.repo, "get_last_reading_before",
            lambda device_id, metric, ts: prime,
        )

        view = svc.get_device_full_view("dev-1", svc.Period.LAST_24H)["energy"]
        bars = svc.bin_consumption(
            view.series, svc.choose_bin(view.window_end - view.window_start),
            view.window_start, view.window_end, view.prime,
        )
        total = sum(b.result.value for b in bars if b.result.is_known)
        assert total == view.period_change


class TestGridWiring:
    def test_layout_provides_the_workspace_slot(self):
        from pages import device_dashboard
        from tests.dash_tree import find_by_id

        assert find_by_id(device_dashboard.layout(), "metric-workspace") is not None

    def test_error_outputs_cover_every_output(self):
        from callbacks.device import error_outputs

        assert len(error_outputs()) == 9
