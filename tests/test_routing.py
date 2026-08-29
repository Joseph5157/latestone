"""Unit tests for URL parsing/building - pure functions, no Dash runtime."""
from __future__ import annotations

from callbacks.routing import PLACEHOLDER_PAGES, device_href, parse_pathname, parse_query
from config.metrics import DEFAULT_METRIC_KEY


class TestParsePathname:
    def test_root_is_overview(self):
        assert parse_pathname("/").name == "overview"

    def test_plants_is_overview(self):
        assert parse_pathname("/plants").name == "overview"

    def test_trailing_slash_is_tolerated(self):
        assert parse_pathname("/plants/").name == "overview"

    def test_plant_detail(self):
        route = parse_pathname("/plants/plant-01")
        assert (route.name, route.plant_id) == ("plant", "plant-01")

    def test_transformer_detail(self):
        route = parse_pathname("/plants/plant-01/plant-01-t1")
        assert route.name == "transformer"
        assert route.plant_id == "plant-01"
        assert route.transformer_id == "plant-01-t1"

    def test_device_dashboard(self):
        route = parse_pathname("/devices/plant-01-t1-d1")
        assert (route.name, route.device_id) == ("device", "plant-01-t1-d1")

    def test_none_pathname_is_overview(self):
        assert parse_pathname(None).name == "overview"

    def test_reports_route(self):
        assert parse_pathname("/reports").name == "reports"
        assert parse_pathname("/reports/").name == "reports"

    def test_notifications_route(self):
        assert parse_pathname("/notifications").name == "notifications"
        assert parse_pathname("/notifications/").name == "notifications"

    def test_command_center_route(self):
        assert parse_pathname("/command-center").name == "command_center"
        assert parse_pathname("/command-center/").name == "command_center"

    def test_admin_devices_route(self):
        assert parse_pathname("/admin/devices").name == "admin_devices"
        assert parse_pathname("/admin/devices/").name == "admin_devices"

    def test_admin_users_route(self):
        assert parse_pathname("/admin/users").name == "admin_users"
        assert parse_pathname("/admin/users/").name == "admin_users"

    def test_admin_with_unknown_child_is_unknown(self):
        assert parse_pathname("/admin/whatever").name == "unknown"

    def test_bare_admin_is_unknown(self):
        assert parse_pathname("/admin").name == "unknown"

    def test_unrecognised_path_is_unknown(self):
        assert parse_pathname("/nope/nope/nope/nope").name == "unknown"

    def test_device_path_without_id_is_unknown(self):
        assert parse_pathname("/devices").name == "unknown"


class TestParseQuery:
    def test_defaults_when_search_is_empty(self):
        assert parse_query("") == (DEFAULT_METRIC_KEY, "24h")

    def test_defaults_when_search_is_none(self):
        assert parse_query(None) == (DEFAULT_METRIC_KEY, "24h")

    def test_reads_metric_and_period(self):
        assert parse_query("?metric=voltage&period=7d") == ("voltage", "7d")

    def test_unknown_metric_falls_back_to_default(self):
        metric, _ = parse_query("?metric=not-a-metric")
        assert metric == DEFAULT_METRIC_KEY

    def test_unknown_period_falls_back_to_24h(self):
        _, period = parse_query("?period=xyz")
        assert period == "24h"


class TestPlaceholderPages:
    def test_notifications_is_no_longer_a_placeholder(self):
        """The Notifications page (pages/notifications.py) is implemented —
        route_to_page must dispatch to it directly rather than falling
        through to the generic placeholder shell."""
        assert "notifications" not in PLACEHOLDER_PAGES


class TestDeviceHref:
    def test_basic_device_href(self):
        assert device_href("plant-01-t1-d1") == "/devices/plant-01-t1-d1"

    def test_device_href_with_metric(self):
        href = device_href("plant-01-t1-d1", metric_key="voltage")
        assert href == "/devices/plant-01-t1-d1?metric=voltage"

    def test_device_href_with_period(self):
        href = device_href("plant-01-t1-d1", period="7d")
        assert href == "/devices/plant-01-t1-d1?period=7d"

    def test_device_href_with_both(self):
        href = device_href("plant-01-t1-d1", metric_key="energy", period="30d")
        assert href == "/devices/plant-01-t1-d1?metric=energy&period=30d"

    def test_device_href_omits_default_metric(self):
        href = device_href("plant-01-t1-d1", metric_key=DEFAULT_METRIC_KEY)
        assert "?" not in href

    def test_device_href_omits_default_period(self):
        href = device_href("plant-01-t1-d1", period="24h")
        assert "?" not in href
