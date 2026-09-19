"""FO-NEW-1: the redesigned Fleet Overview's snapshot. Pure — reads are
monkeypatched, so nothing here opens a connection."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from services import fleet_overview_service as svc
from services.device_scope import DeviceScope
from services.temperature_condition_service import (
    DeviceTemperature,
    TemperatureCondition as C,
    TemperatureLimits,
)

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
LIMITS = TemperatureLimits(Decimal("36"), Decimal("40"))


def _plant(pid, name):
    return SimpleNamespace(plant_id=pid, name=name, country="ZA")


def _t(device, plant="p1", transformer="p1-t1", code="T1", value=30.0, cond=C.NORMAL):
    return DeviceTemperature(
        plant_id=plant, transformer_id=transformer, transformer_code=code,
        device_id=device, device_code=device.upper(), value=value,
        reading_ts=NOW - timedelta(minutes=5), condition=cond,
    )


def _max(transformer, value, device):
    return SimpleNamespace(
        transformer_id=transformer, max_temperature=value,
        max_reading_at=NOW - timedelta(days=3), device_id=device,
    )


def test_groups_plants_transformers_and_loggers():
    temps = [
        _t("d2", value=41.0, cond=C.CRITICAL),
        _t("d1", value=30.0),
        _t("d3", transformer="p1-t2", code="T2", value=None, cond=C.NO_RECENT_DATA),
    ]
    view = svc.build_overview(
        [_plant("p1", "Alpha")], temps, [_max("p1-t1", 44.5, "d2")], now=NOW, limits=LIMITS
    )
    [plant] = view.plants
    assert [t.transformer_code for t in plant.transformers] == ["T1", "T2"]
    assert [l.device_id for l in plant.transformers[0].loggers] == ["d1", "d2"]
    assert plant.transformers[0].max_30d == 44.5
    assert plant.transformers[0].max_30d_device_code == "D2"
    assert plant.transformers[1].max_30d is None
    assert plant.hottest.device_id == "d2"
    assert plant.counts == svc.ConditionCounts(normal=1, hot=1, no_recent_data=1)
    assert (view.transformer_count, view.logger_count) == (2, 3)


def test_plants_without_in_scope_loggers_are_left_out_and_sorted_by_name():
    temps = [_t("a", plant="p2", transformer="p2-t1"), _t("b", plant="p1")]
    view = svc.build_overview(
        [_plant("p1", "zeta"), _plant("p2", "Alpha"), _plant("p3", "Empty")],
        temps, [], now=NOW, limits=None,
    )
    assert [p.name for p in view.plants] == ["Alpha", "zeta"]


def test_hottest_ignores_readings_without_recent_data():
    temps = [_t("old", value=90.0, cond=C.NO_RECENT_DATA), _t("new", value=31.0)]
    [plant] = svc.build_overview([_plant("p1", "A")], temps, [], now=NOW, limits=LIMITS).plants
    assert plant.hottest.device_id == "new"


def test_worst_condition_orders_critical_first():
    assert svc.worst_condition([_t("a"), _t("b", cond=C.WARNING)]) is C.WARNING
    assert svc.worst_condition([_t("a", cond=C.NO_RECENT_DATA), _t("b", cond=C.CRITICAL)]) is C.CRITICAL
    assert svc.worst_condition([]) is None


def test_get_fleet_overview_narrows_every_read_by_the_one_scope(monkeypatch):
    scope = DeviceScope(device_ids=frozenset({"d1"}))
    seen = {}

    def temps(s, *, now):
        seen["temps"] = s
        return [_t("d1")]

    def maxima(**kw):
        seen["max"] = kw
        return []

    def plants(*, scope):
        seen["plants"] = scope
        return [_plant("p1", "A")]

    monkeypatch.setattr(svc, "device_temperatures", temps)
    monkeypatch.setattr(svc.repo, "max_temperature_report_rows", maxima)
    monkeypatch.setattr(svc, "list_plants", plants)
    monkeypatch.setattr(svc, "current_limits", lambda: LIMITS)

    view = svc.get_fleet_overview(scope, now=NOW)

    assert seen["temps"] is scope and seen["plants"] is scope
    assert seen["max"]["allowed_device_ids"] == frozenset({"d1"})
    assert seen["max"]["since"] == NOW - timedelta(days=30)
    assert view.limits == LIMITS and len(view.plants) == 1


def _plant_view(pid, name, hot_value, counts, loggers=2):
    from services.fleet_overview_service import PlantView, TransformerView
    temps = tuple(_t(f"{pid}-d{i}", plant=pid) for i in range(loggers))
    top = _t(f"{pid}-top", plant=pid, value=hot_value) if hot_value is not None else None
    return PlantView(pid, name, "ZA", (TransformerView(f"{pid}-t", "T", None, None, None, temps),),
                     top, counts)


def _polish_view(limits=LIMITS):
    C_ = svc.ConditionCounts
    return svc.FleetOverview(NOW, limits, (
        _plant_view("a", "Alpha", 31.0, C_(normal=2)),
        _plant_view("b", "Bravo", 41.0, C_(normal=1, hot=1)),
        _plant_view("c", "Charlie", None, C_(no_recent_data=2)),
        _plant_view("d", "Delta", 35.0, C_(normal=1, no_recent_data=1)),
    ))


def test_filter_counts_per_available_filter():
    assert svc.filter_counts(_polish_view()) == {
        "all": 4, "hot": 1, "no_recent_data": 2, "normal": 1,
    }


def test_hot_and_normal_filters_need_limits():
    view = _polish_view(limits=None)
    assert svc.available_filters(view) == ("all", "no_recent_data")
    # An unavailable filter falls back to all rather than showing nothing.
    assert len(svc.filter_and_sort(view, "hot", "name")) == 4


def test_filter_keeps_name_order_and_sort_hottest_puts_no_reading_last():
    view = _polish_view()
    assert [p.name for p in svc.filter_and_sort(view, "no_recent_data", "name")] == ["Charlie", "Delta"]
    assert [p.name for p in svc.filter_and_sort(view, "all", "hottest")] == [
        "Bravo", "Delta", "Alpha", "Charlie",
    ]
