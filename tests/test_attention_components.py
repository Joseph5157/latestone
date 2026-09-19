"""CC-NEW-1: structural tests for components/attention.py (no repr())."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from components import attention as ui
from services.attention_service import (
    ActivityItem, AttentionSnapshot, DailyAlarms, Problem, ProblemKind as K,
)
from services.temperature_condition_service import (
    DeviceTemperature, TemperatureCondition as C, TemperatureLimits,
)

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    for child in children if isinstance(children, (list, tuple)) else [children]:
        yield from _walk(child)


def text(node) -> str:
    return " ".join(n for n in _walk(node) if isinstance(n, str))


def classes(node) -> set[str]:
    out = set()
    for n in _walk(node):
        out.update((getattr(n, "className", None) or "").split())
    return out


def hrefs(node) -> list[str]:
    return [n.href for n in _walk(node) if getattr(n, "href", None)]


def _problem(kind=K.POWER_DOWN, hours=2):
    return Problem(kind=kind, device_id="plant-01-t1-d1", device_code="29017",
                   plant_id="plant-01", plant_name="Alpha", transformer_code="T1",
                   since=NOW - timedelta(hours=hours), detail="Unacknowledged")


def _temp(value, condition):
    return DeviceTemperature(plant_id="plant-01", transformer_id="t", transformer_code="T1",
                             device_id="plant-01-t1-d1", device_code="29017", value=value,
                             reading_ts=NOW, condition=condition)


def _snap(problems=(), limits=None, reporting=119):
    return AttentionSnapshot(total_rtls=120, reporting_rtls=reporting, problems=tuple(problems),
                             hottest=(), activity=(), daily_alarms=(), limits=limits,
                             generated_at=NOW)


class TestAgo:
    def test_units(self):
        assert ui.ago(NOW - timedelta(seconds=20), NOW) == "just now"
        assert ui.ago(NOW - timedelta(minutes=15), NOW) == "15 min ago"
        assert ui.ago(NOW - timedelta(hours=3), NOW) == "3 h ago"
        assert ui.ago(NOW - timedelta(days=2, hours=5), NOW) == "2 d ago"
        assert ui.ago(None, NOW) == "—"


class TestStatusBar:
    def test_counts_and_problems(self):
        bar = ui.status_bar(_snap([_problem()]))
        assert "119 of 120 RTLs reporting" in text(bar)
        assert "1 problem" in text(bar)
        assert "attention-status--clear" not in classes(bar)

    def test_all_clear_is_deliberate(self):
        bar = ui.status_bar(_snap([], limits=TemperatureLimits(Decimal("36"), Decimal("40"))))
        assert "All clear" in text(bar)
        assert "attention-status--clear" in classes(bar)

    def test_limits_not_set_is_said_out_loud(self):
        assert "Temperature limits not set" in text(ui.status_bar(_snap([])))

    def test_limits_carry_their_source(self):
        bar = ui.status_bar(_snap([], limits=TemperatureLimits(Decimal("36.5"), Decimal("40"))))
        assert "Warning 36.5 °C" in text(bar) and "Critical 40 °C" in text(bar)
        assert "Limits set by an administrator" in text(bar)


class TestProblemList:
    def test_row_links_to_the_device_and_names_the_problem(self):
        card = ui.problem_list([_problem()], NOW)
        assert "Power Down" in text(card) and "29017" in text(card)
        assert "Alpha · T1" in text(card) and "2 h ago" in text(card)
        assert any(h.startswith("/devices/plant-01-t1-d1") for h in hrefs(card))

    def test_tone_follows_the_kind(self):
        assert "attention-chip--critical" in classes(ui.problem_list([_problem(K.TEMP_CRITICAL)], NOW))
        assert "attention-chip--warning" in classes(ui.problem_list([_problem(K.BATTERY_LOW)], NOW))

    def test_empty_state(self):
        assert "Nothing needs attention" in text(ui.problem_list([], NOW))


class TestHottest:
    def test_values_and_condition(self):
        card = ui.hottest_card([_temp(41.26, C.CRITICAL)])
        assert "41.3 °C" in text(card) and "Critical" in text(card)

    def test_no_chip_when_nothing_is_flagged(self):
        card = ui.hottest_card([_temp(30.0, C.LIMITS_NOT_SET), _temp(30.0, C.NORMAL)])
        assert not any(c.startswith("attention-chip--") for c in classes(card))

    def test_empty(self):
        assert "No recent temperature readings" in text(ui.hottest_card([]))


class TestActivity:
    def test_rows(self):
        item = ActivityItem(NOW - timedelta(minutes=30), "Switched on", "plant-01-t1-d1", "29017", "Alpha")
        card = ui.activity_card([item], NOW)
        assert "Switched on" in text(card) and "30 min ago" in text(card)

    def test_empty(self):
        assert "No activity in the last 24 hours" in text(ui.activity_card([], NOW))


class TestTrend:
    def test_one_bar_per_day_with_its_count(self):
        days = [DailyAlarms(date(2026, 9, 13) + timedelta(days=i), i) for i in range(7)]
        card = ui.alarm_trend_card(days)
        bars = [n for n in _walk(card) if "attention-trend__bar" in (getattr(n, "className", "") or "")]
        assert len(bars) == 7
        assert "6" in text(card) and "Sat 19" in text(card)


def _ids_of(node, type_):
    return [n.id for n in _walk(node) if isinstance(getattr(n, "id", None), dict)
            and n.id.get("type") == type_]


class TestProblemActions:
    def test_no_actions_by_default(self):
        card = ui.problem_list([_problem()], NOW)
        assert _ids_of(card, ui.ACK_BUTTON) == [] and _ids_of(card, ui.MANAGE_BUTTON) == []

    def test_acknowledge_only_for_alarm_kinds_the_user_may_act_on(self):
        problems = [_problem(K.POWER_DOWN), _problem(K.NO_DATA_24H)]
        card = ui.problem_list(problems, NOW, may_ack=frozenset({"plant-01-t1-d1"}))
        assert _ids_of(card, ui.ACK_BUTTON) == [
            {"type": ui.ACK_BUTTON, "device": "plant-01-t1-d1", "kind": "power_down"}]

    def test_manage_for_permitted_devices(self):
        card = ui.problem_list([_problem(K.NO_DATA_24H)], NOW,
                               may_manage=frozenset({"plant-01-t1-d1"}))
        assert _ids_of(card, ui.MANAGE_BUTTON) == [
            {"type": ui.MANAGE_BUTTON, "device": "plant-01-t1-d1"}]

    def test_devices_outside_the_sets_get_no_buttons(self):
        card = ui.problem_list([_problem(K.POWER_DOWN)], NOW,
                               may_ack=frozenset({"other"}), may_manage=frozenset({"other"}))
        assert _ids_of(card, ui.ACK_BUTTON) == [] and _ids_of(card, ui.MANAGE_BUTTON) == []


def test_status_bar_counts_problems_by_severity_including_zeros():
    snap = _snap(problems=[_problem(K.POWER_DOWN), _problem(K.POWER_DOWN), _problem(K.BATTERY_LOW)])
    counters = [n for n in _walk(ui.status_bar(snap)) if "attention-counter" in (getattr(n, "className", "") or "").split()]
    assert [text(c) for c in counters] == ["Critical 2", "Warning 1", "No data 0", "Sensor 0"]


def test_problem_list_has_a_column_header_on_the_row_grid():
    card = ui.problem_list([_problem()], NOW)
    assert "attention-problem--head" in classes(card)
    assert "Since" in text(card)


def test_empty_problem_list_has_no_header():
    assert "attention-problem--head" not in classes(ui.problem_list([], NOW))


def test_status_bar_names_the_oldest_unacknowledged_alarm_and_the_ack_count():
    snap = _snap(problems=[_problem(K.POWER_DOWN, hours=3), _problem(K.BATTERY_LOW, hours=50),
                           _problem(K.NO_DATA_24H, hours=90)])
    snap = AttentionSnapshot(**{**snap.__dict__, "acknowledged_24h": 4})
    content = text(ui.status_bar(snap))
    # No-data is not an alarm to acknowledge, so the 90 h one is skipped.
    assert "Oldest unacknowledged: Battery Low · 2 d ago" in content
    assert "4 acknowledged in the last 24 h" in content


def test_status_bar_says_when_nothing_awaits_acknowledgement():
    assert "No unacknowledged alarms" in text(ui.status_bar(_snap()))
