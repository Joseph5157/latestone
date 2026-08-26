"""UI-4 presentation contracts for the Device Detail hierarchy."""
from __future__ import annotations

from pages import device_dashboard
from tests.dash_tree import find_by_class, find_by_id, text_of


def _layout(period: str = "24h"):
    return device_dashboard.layout(
        plant_name="Grand Coulee",
        transformer_code="un01",
        device_code="29017",
        metric_key="temperature",
        period=period,
        plant_id="plant-07",
        transformer_id="plant-07-t1",
        device_status="active",
    )


def test_device_identity_is_the_page_heading():
    layout = _layout()
    headings = find_by_class(layout, "device-page-heading__title")
    assert len(headings) == 1
    assert text_of(headings[0]) == "29017"
    assert "RTL device" in text_of(find_by_class(layout, "device-page-heading")[0])


def test_sections_express_the_operational_hierarchy():
    layout = _layout()
    assert "Current state" in text_of(find_by_class(layout, "device-current-state")[0])
    assert "Metric workspace" in text_of(find_by_class(layout, "device-current-state")[0])
    assert "Metric history" in text_of(find_by_class(layout, "device-telemetry")[0])
    assert "Recent readings" in text_of(find_by_class(layout, "device-readings")[0])


def test_existing_dynamic_slots_remain_present_once():
    layout = _layout()
    for component_id in (
        "equipment-last-data", "metric-workspace", "metric-dropdown", "period-radio",
        "custom-range-container", "custom-date-range", "kpi-row-container",
        "metric-chart", "readings-table", "device-refresh-interval",
    ):
        assert find_by_id(layout, component_id) is not None, component_id


def test_controls_are_labeled_without_changing_values():
    layout = _layout("7d")
    controls = find_by_class(layout, "metric-controls")[0]
    assert "Metric" in text_of(controls)
    assert "Time range" in text_of(controls)
    period = find_by_id(layout, "period-radio")
    assert period.value == "7d"
    assert [option["value"] for option in period.options] == ["24h", "7d", "30d", "custom"]


def test_administrative_status_has_a_neutral_axis_hook():
    context = find_by_class(_layout(), "equipment-context")[0]
    status_items = find_by_class(context, "equipment-context__item--administrative")
    assert len(status_items) == 1
    assert "Status" in text_of(status_items[0])
    assert "active" in text_of(status_items[0])


def test_unresolved_device_heading_is_intentional():
    heading = find_by_class(device_dashboard.layout(), "device-page-heading__title")[0]
    assert text_of(heading) == "Device"
