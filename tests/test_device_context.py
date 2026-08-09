"""Device dashboard must show its equipment identity and navigable parents.

Regression tests for audit finding NEW-06.

UI_SPEC 6a requires the context bar to show
`Plant Name | Transformer Code | Device Code | Status`. The implementation had
been reduced to `Last data: <timestamp>`, and the device breadcrumb rendered
Plant and Transformer as plain text, so there was no way back up the hierarchy
from a device — even though `DevicePath` already carries `plant_id` and
`transformer_id`.

The three status concepts stay separate per CLAUDE.md: the bar shows
administrative status, the header badge shows data freshness, and monitoring
condition remains UNKNOWN elsewhere.
"""
from __future__ import annotations

from callbacks.routing import build_device_context
from pages import device_dashboard
from repositories.plant_monitoring_repository import DevicePath

from tests.dash_tree import find_by_class, find_by_id, links, text_of

DEVICE_PATH = DevicePath(
    plant_id="plant-07",
    plant_name="Grand Coulee",
    transformer_id="plant-07-t1",
    transformer_code="un01",
    device_id="plant-07-t1-d1",
    device_code="29017",
    device_status="active",
)


def _layout():
    return device_dashboard.layout(
        plant_name=DEVICE_PATH.plant_name,
        transformer_code=DEVICE_PATH.transformer_code,
        device_code=DEVICE_PATH.device_code,
        metric_key="temperature",
        period="24h",
        plant_id=DEVICE_PATH.plant_id,
        transformer_id=DEVICE_PATH.transformer_id,
        device_status=DEVICE_PATH.device_status,
    )


class TestRouterPassesTheFullPath:
    def test_context_carries_the_parent_ids(self):
        """The router used to drop these, so the layout could not link upward."""
        ctx = build_device_context(DEVICE_PATH, "temperature", "24h")
        assert ctx["plant_id"] == "plant-07"
        assert ctx["transformer_id"] == "plant-07-t1"

    def test_context_carries_administrative_status(self):
        ctx = build_device_context(DEVICE_PATH, "temperature", "24h")
        assert ctx["device_status"] == "active"

    def test_context_keeps_the_existing_fields(self):
        ctx = build_device_context(DEVICE_PATH, "temperature", "24h")
        assert ctx["route"] == "device"
        assert ctx["device_id"] == "plant-07-t1-d1"
        assert ctx["plant_name"] == "Grand Coulee"
        assert ctx["transformer_code"] == "un01"
        assert ctx["metric_key"] == "temperature"
        assert ctx["period"] == "24h"


class TestEquipmentContextBar:
    def test_bar_shows_all_four_required_fields(self):
        bar = find_by_class(_layout(), "equipment-context")[0]
        text = text_of(bar)
        for expected in ("Grand Coulee", "un01", "29017", "active"):
            assert expected in text, f"context bar is missing {expected!r}"

    def test_bar_labels_each_field(self):
        bar = find_by_class(_layout(), "equipment-context")[0]
        text = text_of(bar)
        for label in ("Plant", "Transformer", "Device", "Status"):
            assert label in text

    def test_last_data_slot_is_retained(self):
        """Last data was the only surviving field; it must not be lost."""
        layout = _layout()
        assert find_by_id(layout, "equipment-last-data") is not None
        assert "Last data" in text_of(find_by_class(layout, "equipment-context")[0])

    def test_bar_degrades_without_optional_context(self):
        """A layout built before the path resolves must still render."""
        bar = find_by_class(device_dashboard.layout(), "equipment-context")[0]
        assert text_of(bar).strip() != ""


class TestDeviceBreadcrumbIsNavigable:
    def test_plant_and_transformer_are_links(self):
        crumb = find_by_class(_layout(), "breadcrumb")[0]
        hrefs = dict(links(crumb))
        assert hrefs.get("Fleet") == "/plants"
        assert hrefs.get("Grand Coulee") == "/plants/plant-07"
        assert hrefs.get("un01") == "/plants/plant-07/plant-07-t1"

    def test_the_device_itself_is_not_a_link(self):
        crumb = find_by_class(_layout(), "breadcrumb")[0]
        assert "29017" not in dict(links(crumb))

    def test_parents_are_plain_text_when_ids_are_unknown(self):
        """Without ids we must not emit a broken href."""
        layout = device_dashboard.layout(
            plant_name="Grand Coulee", transformer_code="un01", device_code="29017",
        )
        crumb = find_by_class(layout, "breadcrumb")[0]
        hrefs = dict(links(crumb))
        assert hrefs.get("Fleet") == "/plants"
        assert "Grand Coulee" not in hrefs
        assert "un01" not in hrefs
