"""FO-NEW-1: structural tests for components/fleet_overview.py (no repr())."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from dash import html

from components import fleet_overview as ui
from services.fleet_overview_service import (
    ConditionCounts, FleetOverview, PlantView, TransformerView,
)
from services.temperature_condition_service import (
    LIMIT_SOURCE_NOTE, DeviceTemperature, TemperatureCondition as C, TemperatureLimits,
)

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
LIMITS = TemperatureLimits(Decimal("36"), Decimal("40.000"))


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    for child in children if isinstance(children, (list, tuple)) else [children]:
        yield from _walk(child)


def text(node) -> str:
    return " ".join(n for n in _walk(node) if isinstance(n, str))


def hrefs(node) -> list[str]:
    return [n.href for n in _walk(node) if getattr(n, "href", None)]


def _t(device="d1", value=41.26, cond=C.CRITICAL):
    return DeviceTemperature("p1", "p1-t1", "T1", device, device.upper(), value,
                             NOW - timedelta(minutes=12), cond)


def _view(limits=LIMITS, plants=None):
    logger = _t()
    tv = TransformerView("p1-t1", "T1", 44.5, datetime(2026, 9, 16, 14, 0, tzinfo=timezone.utc),
                         "D1", (logger,))
    plant = PlantView("p1", "Alpha Station", "ZA", (tv,), logger,
                      ConditionCounts(normal=2, hot=1, no_recent_data=1))
    return FleetOverview(NOW, limits, (plant,) if plants is None else plants)


def test_limits_line_names_the_values_and_their_source():
    line = text(ui.limits_line(LIMITS))
    assert "36 °C" in line and "40 °C" in line and LIMIT_SOURCE_NOTE in line


def test_limits_line_says_when_limits_are_not_set():
    assert "not set" in text(ui.limits_line(None))


def test_plant_row_is_a_disclosure_with_temperature_first():
    [row] = ui.plant_list(_view()).children
    assert isinstance(row, html.Details)
    summary = text(row.children[0])
    assert "Alpha Station" in summary and "41.3 °C" in summary and "Critical" in summary
    assert "2 normal · 1 hot · 1 without recent data" in summary


def test_expanded_plant_shows_transformer_peak_and_rtl_rows():
    [row] = ui.plant_list(_view()).children
    body = row.children[1]
    content = text(body)
    assert "Transformer T1" in content
    assert "30-day max 44.5 °C on 16 Sep 14:00 UTC (RTL D1)" in content
    assert "12 min ago" in content and "Electrical readings →" in content
    assert hrefs(body).count("/devices/d1") == 2


def test_no_alarm_or_electrical_values_on_the_page():
    content = text(ui.plant_list(_view())).lower()
    for word in ("voltage", "current", "power down", "battery", "acknowledge"):
        assert word not in content


def test_counts_hide_normal_and_hot_when_limits_are_not_set():
    counts = ConditionCounts(limits_not_set=3, no_recent_data=1)
    assert ui.counts_text(counts, limits_set=False) == "1 without recent data"


def test_empty_scope_says_so():
    assert "No plants" in text(ui.plant_list(_view(plants=())))


def test_filter_options_carry_counts_and_hide_hot_without_limits():
    assert [o["label"] for o in ui.filter_options(_view(limits=None))] == [
        "All · 1", "No recent data · 1",
    ]
    assert [o["value"] for o in ui.filter_options(_view())] == [
        "all", "hot", "no_recent_data", "normal",
    ]


def test_an_empty_filter_result_says_so_rather_than_no_plants():
    assert "No plants match" in text(ui.plant_list(_view(), plants=()))


def test_stat_cards_are_temperature_first_and_count_rtls():
    cards = ui.stat_cards(_view())
    content = text(cards)
    assert "Hottest now" in content and "41.3 °C" in content and "Alpha Station" in content
    assert "Hot RTLs" in content and "1 Critical · 0 Warning" in content
    assert "30-day peak" in content and "44.5 °C" in content
    assert "Reporting" in content and "1 of 1" in content


def test_stat_cards_without_limits_do_not_invent_hot_counts():
    content = text(ui.stat_cards(_view(limits=None)))
    assert "Temperature limits not set" in content


def _jump_ids(node):
    return [n.id for n in _walk(node)
            if isinstance(getattr(n, "id", None), dict) and n.id.get("type") == ui.JUMP]


def test_cards_that_filter_are_buttons_with_their_target():
    targets = {(i["part"], i["filter"], i["sort"]) for i in _jump_ids(ui.stat_cards(_view()))}
    assert targets == {("hottest", "", "hottest"), ("hot", "hot", ""), ("reporting", "no_recent_data", "")}


def test_peak_card_carries_its_full_text_on_hover():
    peak = [n for n in _walk(ui.stat_cards(_view())) if getattr(n, "title", None)
            and "30-day" not in str(getattr(n, "title", ""))]
    assert any("16 Sep 14:00 UTC · RTL D1 · Alpha Station" == n.title for n in peak)


def test_condition_bar_segments_and_legend_select_the_matching_chip():
    bar = ui.condition_bar(_view())
    ids = _jump_ids(bar)
    assert {i["filter"] for i in ids} == {"hot"}  # the one RTL is Critical
    assert "Critical temperature 1" in text(bar) and "1 RTL" in text(bar)


def test_limits_not_set_segment_is_not_clickable():
    from services.temperature_condition_service import TemperatureCondition as TC
    logger = DeviceTemperature("p1", "p1-t1", "T1", "d1", "D1", 30.0, NOW, TC.LIMITS_NOT_SET)
    tv = TransformerView("p1-t1", "T1", None, None, None, (logger,))
    plant = PlantView("p1", "A", "ZA", (tv,), logger, ConditionCounts(limits_not_set=1))
    bar = ui.condition_bar(FleetOverview(NOW, None, (plant,)))
    assert _jump_ids(bar) == [] and "Limits not set 1" in text(bar)
