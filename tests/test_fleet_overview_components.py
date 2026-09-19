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


def test_summary_counts_plants_transformers_and_rtls():
    assert ui.summary_line(_view()) == "1 plant · 1 transformer · 1 RTL"


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
