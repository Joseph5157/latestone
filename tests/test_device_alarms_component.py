"""ALARM-HISTORY-1 (ADR-027): the Device page's alarm history list and the
chart overlay. Structural assertions only — no database connection."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from components import device_alarms as ui
from components.metric_chart import add_alarm_overlay, build_metric_figure
from config.metrics import get_metric
from services.attention_service import ProblemKind as K
from services.device_timeline_service import DeviceAlarm, ReadingGap
from services.monitoring_service import Reading

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
ALARMS = (
    DeviceAlarm(3, K.BATTERY_LOW, NOW - timedelta(hours=1), None),
    DeviceAlarm(2, K.POWER_DOWN, NOW - timedelta(days=2), NOW - timedelta(days=2) + timedelta(hours=6)),
    DeviceAlarm(1, K.SENSOR_ERROR, NOW - timedelta(days=4), NOW - timedelta(days=4) + timedelta(minutes=55)),
)


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    for child in children if isinstance(children, (list, tuple)) else [children]:
        yield from _walk(child)


def text(node) -> str:
    return " ".join(n for n in _walk(node) if isinstance(n, str))


def _by_class(node, cls):
    return [n for n in _walk(node) if cls in (getattr(n, "className", "") or "").split()]


class TestAlarmHistory:
    def test_rows_newest_first_with_time_kind_and_acknowledgement(self):
        section = ui.alarm_history(ALARMS, "Last 7 days")
        rows = _by_class(section, "device-alarms__row")
        assert len(rows) == 3
        assert "19 Sep 11:00 UTC" in text(rows[0])
        assert "Battery Low" in text(rows[0]) and "Unacknowledged" in text(rows[0])
        assert "Acknowledged 6 h later" in text(rows[1])
        assert "Acknowledged 55 min later" in text(rows[2])

    def test_kind_takes_its_tone_and_summary_counts_open_alarms(self):
        section = ui.alarm_history(ALARMS, "Last 7 days")
        kinds = _by_class(section, "device-alarms__kind")
        assert "status-text--warning" in kinds[0].className
        assert "status-text--critical" in kinds[1].className
        assert "Alarm history · Last 7 days" in text(section)
        assert "3 alarms · 1 unacknowledged" in text(section)

    def test_empty_period_says_so(self):
        section = ui.alarm_history((), "Last 24 hours")
        assert "No alarms in this period." in text(section)
        assert _by_class(section, "device-alarms__row") == []

    def test_general_user_gets_nothing(self):
        assert ui.alarm_history(None, "Last 7 days") is None


class TestChartOverlay:
    def _fig(self):
        series = [Reading(NOW - timedelta(minutes=30 * i), 30.0) for i in range(10)]
        return build_metric_figure(get_metric("temperature"), series)

    def test_one_line_per_alarm_and_one_band_per_gap(self):
        fig = self._fig()
        gap = ReadingGap(NOW - timedelta(hours=8), NOW - timedelta(hours=3))
        add_alarm_overlay(fig, ALARMS, (gap,))
        lines = [s for s in fig.layout.shapes if s.type == "line"]
        bands = [s for s in fig.layout.shapes if s.type == "rect"]
        assert len(lines) == 3 and len(bands) == 1
        assert lines[0].line.color == "#d97706"  # Battery Low, warning tone
        assert [a.text for a in fig.layout.annotations] == ["No readings"]

    def test_markers_carry_the_alarm_name_for_hover(self):
        fig = self._fig()
        add_alarm_overlay(fig, ALARMS, ())
        markers = [t for t in fig.data if t.name in {"Power Down", "Battery Low", "Sensor Error"}]
        assert {t.name for t in markers} == {"Power Down", "Battery Low", "Sensor Error"}
        assert all(t.yaxis == "y2" for t in markers)
        assert fig.layout.yaxis2.visible is False

    def test_nothing_to_add(self):
        fig = self._fig()
        before = len(fig.data)
        add_alarm_overlay(fig, (), ())
        assert len(fig.data) == before and not fig.layout.shapes
