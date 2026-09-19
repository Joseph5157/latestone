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


def find_by_class(node, name: str):
    return next(n for n in _walk(node)
                if name in (getattr(n, "className", None) or "").split())


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
        assert "RTLs reporting" not in text(bar)  # WORKING-CARD-1: now a card
        assert "1 problem" in text(bar)
        assert "attention-status--clear" not in classes(bar)

    def test_working_card_counts_reporting_rtls(self):
        bar = ui.status_bar(_snap([_problem()]))
        card = find_by_class(bar, "attention-working")
        assert "Working" in text(card)
        assert "119 of 120" in text(card)
        assert "1 not reporting" in text(card)
        assert "attention-working--short" in classes(card)

    def test_working_card_all_reporting(self):
        card = find_by_class(ui.status_bar(_snap(reporting=120)), "attention-working")
        assert "120 of 120" in text(card)
        assert "All RTLs reporting" in text(card)
        assert "attention-working--short" not in classes(card)

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

    def test_tone_follows_the_kind_as_text_colour_not_a_badge(self):
        # ADR-026 (COLOUR-KEY-3): the problem is the row's main text, so the
        # text takes the tone; badges are for a status beside a value.
        critical = classes(ui.problem_list([_problem(K.TEMP_CRITICAL)], NOW))
        assert "status-text--critical" in critical
        assert "status-text--warning" in classes(ui.problem_list([_problem(K.BATTERY_LOW)], NOW))
        assert not any(c.startswith(("status-chip", "status-dot")) for c in critical)

    def test_the_problem_name_stays_readable_text(self):
        card = ui.problem_list([_problem(K.POWER_DOWN)], NOW)
        assert "Power Down" in text(card)

    def test_empty_state(self):
        assert "Nothing needs attention" in text(ui.problem_list([], NOW))


class TestHottest:
    def test_values_and_condition(self):
        card = ui.hottest_card([_temp(41.26, C.CRITICAL)])
        assert "41.3 °C" in text(card) and "Critical" in text(card)

    def test_no_chip_when_nothing_is_flagged(self):
        card = ui.hottest_card([_temp(30.0, C.LIMITS_NOT_SET), _temp(30.0, C.NORMAL)])
        assert not any(c.startswith("status-chip--") for c in classes(card))

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
    assert [text(c) for c in counters] == [
        "Critical 2 Power Down 2", "Warning 1 Battery Low 1",
        "No data 0 None right now", "Device fault 0 None right now",
    ]


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


def _by_class(node, cls):
    return [n for n in _walk(node) if cls in (getattr(n, "className", "") or "").split()]


def test_severity_strip_segments_follow_the_counts_or_read_clear():
    busy = ui.status_bar(_snap(problems=[_problem(K.POWER_DOWN), _problem(K.POWER_DOWN), _problem(K.BATTERY_LOW)]))
    segs = _by_class(busy, "attention-strip__seg")
    assert [(s.className.split("--")[-1], s.style["flexGrow"]) for s in segs] == [("critical", 2), ("warning", 1)]
    clear = _by_class(ui.status_bar(_snap()), "attention-strip__seg")
    assert [s.className.split("--")[-1] for s in clear] == ["normal"]


def test_hottest_meter_places_limit_markers_and_fills_to_the_value():
    limits = TemperatureLimits(Decimal("36"), Decimal("40"))
    card = ui.hottest_card([_temp(40.1, C.CRITICAL), _temp(31.0, C.NORMAL)], limits)
    marks = _by_class(card, "attention-meter__mark")
    assert len(marks) == 4  # warning + critical on each of two rows
    low, high = ui.temperature_scale([_temp(40.1, C.CRITICAL), _temp(31.0, C.NORMAL)], limits)
    assert low <= 31.0 and high >= 40.1
    fills = _by_class(card, "attention-meter__fill")
    assert float(fills[0].style["width"].rstrip("%")) > float(fills[1].style["width"].rstrip("%"))
    assert "Markers: Warning 36 °C · Critical 40 °C" in text(card)


def test_hottest_meter_has_no_markers_without_limits():
    card = ui.hottest_card([_temp(33.0, C.LIMITS_NOT_SET)])
    assert _by_class(card, "attention-meter__mark") == []
    assert len(_by_class(card, "attention-meter__fill")) == 1


def test_trend_bars_stack_by_kind_with_a_legend():
    day = DailyAlarms(date(2026, 9, 19), 3, ((K.POWER_DOWN, 1), (K.BATTERY_LOW, 2)))
    card = ui.alarm_trend_card([day])
    segs = _by_class(card, "attention-trend__seg")
    assert [s.style["flexGrow"] for s in segs] == [1, 2]
    assert "Power Down" in text(card) and "Battery Low" in text(card)


def test_counters_are_filter_buttons_and_the_active_one_is_pressed():
    snap = _snap(problems=[_problem(K.POWER_DOWN), _problem(K.BATTERY_LOW)])
    bar = ui.status_bar(snap, selected="critical")
    counters = {n.id["tone"]: n for n in _walk(bar)
                if isinstance(getattr(n, "id", None), dict) and n.id.get("part") == "counter"}
    assert counters["critical"].__dict__["aria-pressed"] == "true"
    assert counters["warning"].__dict__["aria-pressed"] == "false"
    assert counters["nodata"].disabled is True  # nothing to show
    strip = [n for n in _walk(bar) if isinstance(getattr(n, "id", None), dict) and n.id.get("part") == "strip"]
    assert "attention-strip__seg--dim" in strip[1].className  # warning dimmed while critical is selected


def test_selected_severity_narrows_the_list_and_offers_show_all():
    problems = [_problem(K.POWER_DOWN), _problem(K.BATTERY_LOW), _problem(K.TEMP_CRITICAL)]
    card = ui.problem_list(problems, NOW, selected="critical")
    assert len(_by_class(card, "attention-problem")) == 3  # header + 2 critical rows
    assert "Showing Critical only · 2 problems" in text(card)
    assert any(isinstance(getattr(n, "id", None), dict) and n.id.get("tone") == "all" for n in _walk(card))


def test_no_selection_shows_everything_without_a_note():
    card = ui.problem_list([_problem(K.POWER_DOWN), _problem(K.BATTERY_LOW)], NOW)
    assert "Showing" not in text(card)


def test_severity_cards_break_each_tone_down_by_kind_in_rank_order():
    snap = _snap(problems=[_problem(K.POWER_DOWN), _problem(K.TEMP_CRITICAL), _problem(K.TEMP_CRITICAL)])
    assert ui.severity_breakdown(snap.problems)["critical"] == "Critical temperature 2 · Power Down 1"
    cards = [c for c in _by_class(ui.status_bar(snap), "attention-severity-card")
             if "attention-working" not in (c.className or "").split()]
    assert len(cards) == 4
