"""Tests for Notification Center — config, service, page, callbacks.

All tests exercise pure logic (no Dash runtime, no database, no notification service).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from config.notifications import (
    CATEGORIES,
    all_categories,
    derivable_categories,
    backend_required_categories,
    get_category,
)
from services.notification_service import (
    NO_DATA_NOTIFICATION_AFTER,
    NotificationRow,
    build_no_data_notifications,
    build_current_notifications,
    notification_summary,
)
from pages.notifications import layout
from routes import device_href

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Notification config — config/notifications.py
# ---------------------------------------------------------------------------

class TestNotificationConfig:
    def test_six_categories_exist(self):
        assert len(CATEGORIES) == 6

    def test_no_data_24h_category(self):
        cat = get_category("no_data_24h")
        assert cat is not None
        assert cat.label == ">24h No Data"
        assert cat.derivable_from_frontend_data is True
        assert cat.backend_required is False

    def test_battery_alarm_category(self):
        cat = get_category("battery_alarm")
        assert cat is not None
        assert cat.label == "Battery Alarm"
        assert cat.derivable_from_frontend_data is False
        assert cat.backend_required is True

    def test_power_down_category(self):
        cat = get_category("power_down")
        assert cat is not None
        assert cat.label == "Power Down"
        assert cat.derivable_from_frontend_data is False
        assert cat.backend_required is True

    def test_sensor_error_category(self):
        cat = get_category("sensor_error")
        assert cat is not None
        assert cat.label == "Sensor Error"
        assert cat.derivable_from_frontend_data is False
        assert cat.backend_required is True

    def test_startup_checkin_category(self):
        cat = get_category("startup_checkin")
        assert cat is not None
        assert cat.label == "Startup / Check-In"
        assert cat.derivable_from_frontend_data is False
        assert cat.backend_required is True

    def test_message_forwarding_category(self):
        cat = get_category("message_forwarding")
        assert cat is not None
        assert cat.label == "Message Forwarding"
        assert cat.derivable_from_frontend_data is False
        assert cat.backend_required is True

    def test_no_invented_high_temp_vibration(self):
        keys = [c.key for c in CATEGORIES]
        assert "high_temperature" not in keys
        assert "vibration" not in keys

    def test_no_warning_critical_severity(self):
        for cat in CATEGORIES:
            assert not hasattr(cat, "severity") or getattr(cat, "severity", None) is None

    def test_unknown_category_returns_none(self):
        assert get_category("nonexistent") is None

    def test_all_categories_returns_all(self):
        assert len(all_categories()) == 6

    def test_derivable_categories(self):
        derivable = derivable_categories()
        assert len(derivable) == 1
        assert derivable[0].key == "no_data_24h"

    def test_backend_required_categories(self):
        backend = backend_required_categories()
        assert len(backend) == 5


# ---------------------------------------------------------------------------
# Notification service — >24h rule
# ---------------------------------------------------------------------------

class TestNoDataNotificationRule:
    def test_24h_constant(self):
        assert NO_DATA_NOTIFICATION_AFTER == timedelta(hours=24)

    def test_reading_older_than_24h_creates_notification(self):
        class MockRow:
            def __init__(self, device_id, reading_ts, plant_id="p1", transformer_id="t1"):
                self.device_id = device_id
                self.reading_ts = reading_ts
                self.plant_id = plant_id
                self.transformer_id = transformer_id

        old_ts = NOW - timedelta(hours=25)
        rows = [MockRow("d1", old_ts)]
        notifications = build_no_data_notifications(rows, NOW)
        assert len(notifications) == 1
        assert notifications[0].entity_id == "d1"
        assert notifications[0].notification_type == ">24h No Data"

    def test_reading_exactly_24h_creates_notification(self):
        class MockRow:
            def __init__(self, device_id, reading_ts, plant_id="p1", transformer_id="t1"):
                self.device_id = device_id
                self.reading_ts = reading_ts
                self.plant_id = plant_id
                self.transformer_id = transformer_id

        exactly_24h = NOW - timedelta(hours=24)
        rows = [MockRow("d1", exactly_24h)]
        notifications = build_no_data_notifications(rows, NOW)
        # Exactly 24h should NOT trigger (> not >=)
        assert len(notifications) == 0

    def test_reading_23h59m_does_not_create_notification(self):
        class MockRow:
            def __init__(self, device_id, reading_ts, plant_id="p1", transformer_id="t1"):
                self.device_id = device_id
                self.reading_ts = reading_ts
                self.plant_id = plant_id
                self.transformer_id = transformer_id

        fresh_ts = NOW - timedelta(hours=23, minutes=59)
        rows = [MockRow("d1", fresh_ts)]
        notifications = build_no_data_notifications(rows, NOW)
        assert len(notifications) == 0

    def test_never_reported_device_excluded(self):
        class MockRow:
            def __init__(self, device_id, reading_ts, plant_id="p1", transformer_id="t1"):
                self.device_id = device_id
                self.reading_ts = reading_ts
                self.plant_id = plant_id
                self.transformer_id = transformer_id

        rows = [MockRow("d1", None)]
        notifications = build_no_data_notifications(rows, NOW)
        assert len(notifications) == 0

    def test_one_row_per_affected_device(self):
        class MockRow:
            def __init__(self, device_id, reading_ts, plant_id="p1", transformer_id="t1"):
                self.device_id = device_id
                self.reading_ts = reading_ts
                self.plant_id = plant_id
                self.transformer_id = transformer_id

        old_ts = NOW - timedelta(hours=30)
        rows = [
            MockRow("d1", old_ts),
            MockRow("d1", old_ts),
            MockRow("d1", old_ts),
        ]
        notifications = build_no_data_notifications(rows, NOW)
        # One device, one row regardless of how many rows
        assert len(notifications) == 1

    def test_stale_threshold_does_not_affect_24h_rule(self):
        """The formal >24h rule is independent of the STALE threshold."""
        class MockRow:
            def __init__(self, device_id, reading_ts, plant_id="p1", transformer_id="t1"):
                self.device_id = device_id
                self.reading_ts = reading_ts
                self.plant_id = plant_id
                self.transformer_id = transformer_id

        # Reading is 20h old — may be STALE (threshold is 90min) but NOT >24h
        stale_but_not_24h = NOW - timedelta(hours=20)
        rows = [MockRow("d1", stale_but_not_24h)]
        notifications = build_no_data_notifications(rows, NOW)
        assert len(notifications) == 0

    def test_device_href_in_notification(self):
        class MockRow:
            def __init__(self, device_id, reading_ts, plant_id="p1", transformer_id="t1"):
                self.device_id = device_id
                self.reading_ts = reading_ts
                self.plant_id = plant_id
                self.transformer_id = transformer_id

        old_ts = NOW - timedelta(hours=25)
        rows = [MockRow("d1", old_ts)]
        notifications = build_no_data_notifications(rows, NOW)
        assert notifications[0].href == device_href("d1")

    def test_deterministic_ordering(self):
        class MockRow:
            def __init__(self, device_id, reading_ts, plant_id="p1", transformer_id="t1"):
                self.device_id = device_id
                self.reading_ts = reading_ts
                self.plant_id = plant_id
                self.transformer_id = transformer_id

        old_ts = NOW - timedelta(hours=30)
        rows = [
            MockRow("d3", old_ts),
            MockRow("d1", old_ts),
            MockRow("d2", old_ts),
        ]
        notifications = build_no_data_notifications(rows, NOW)
        ids = [n.entity_id for n in notifications]
        assert ids == ["d1", "d2", "d3"]


# ---------------------------------------------------------------------------
# Notification service — build_current_notifications
# ---------------------------------------------------------------------------

class TestBuildCurrentNotifications:
    def test_returns_list(self):
        assert isinstance(build_current_notifications([], NOW), list)

    def test_includes_no_data_24h(self):
        class MockRow:
            def __init__(self, device_id, reading_ts, plant_id="p1", transformer_id="t1"):
                self.device_id = device_id
                self.reading_ts = reading_ts
                self.plant_id = plant_id
                self.transformer_id = transformer_id

        old_ts = NOW - timedelta(hours=25)
        rows = [MockRow("d1", old_ts)]
        notifications = build_current_notifications(rows, NOW)
        assert len(notifications) == 1
        assert notifications[0].notification_type == ">24h No Data"


# ---------------------------------------------------------------------------
# Notification summary
# ---------------------------------------------------------------------------

class TestNotificationSummary:
    def test_empty_summary(self):
        summary = notification_summary([])
        assert summary["total"] == 0

    def test_summary_with_notifications(self):
        rows = [
            NotificationRow(
                key="test",
                entity_id="d1",
                entity_label="Device 1",
                entity_type="Device",
                notification_type=">24h No Data",
                detail="test",
                occurred_at=None,
                href="/devices/d1",
            )
        ]
        summary = notification_summary(rows)
        assert summary["total"] == 1


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

class TestNotificationsPageLayout:
    def test_layout_returns_component(self):
        lay = layout()
        assert hasattr(lay, "children")

    def test_layout_has_breadcrumb(self):
        lay = layout()
        assert "breadcrumb" in str(lay).lower() or "Notification Center" in str(lay)

    def test_layout_has_prototype_notice(self):
        lay = layout()
        text = str(lay)
        assert "Prototype" in text or "prototype" in text

    def test_layout_has_formal_notifications_section(self):
        lay = layout()
        text = str(lay)
        assert "Formal Notifications" in text

    def test_layout_has_supported_types_section(self):
        lay = layout()
        text = str(lay)
        assert "Supported Notification Types" in text

    def test_layout_has_notification_table(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "notification-table" in ids

    def test_layout_has_supported_types_table(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "supported-types-table" in ids

    def test_layout_has_summary(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "notification-summary" in ids

    def test_layout_has_empty_state(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "notification-empty" in ids

    def test_layout_has_error_slot(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "notification-error" in ids

    def test_no_sms_email_backend_claims(self):
        lay = layout()
        text = str(lay).lower()
        assert "sms" not in text
        assert "email" not in text
        assert "rabbitmq" not in text
        assert "mqtt" not in text


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------

class TestArchitecture:
    def test_no_sql_in_page_module(self):
        import pages.notifications as mod
        import inspect
        source = inspect.getsource(mod)
        assert "from sqlalchemy import text" not in source
        assert "session.execute" not in source

    def test_no_sql_in_callback_module(self):
        import callbacks.notifications as mod
        import inspect
        source = inspect.getsource(mod)
        assert "from sqlalchemy import text" not in source
        assert "session.execute" not in source

    def test_no_file_output_in_callbacks(self):
        import callbacks.notifications as mod
        import inspect
        source = inspect.getsource(mod)
        assert "open(" not in source
        assert "write(" not in source

    def test_notification_config_independent_of_backend(self):
        import config.notifications as mod
        import inspect
        source = inspect.getsource(mod)
        assert "repository" not in source.lower()
        assert "database" not in source.lower()
        assert "sql" not in source.lower()

    def test_notification_service_uses_existing_freshness(self):
        import services.notification_service as mod
        import inspect
        source = inspect.getsource(mod)
        assert "from services.monitoring_service import" in source

    def test_stale_threshold_not_reused(self):
        """The 24h rule uses its own constant, not the STALE threshold."""
        import services.notification_service as mod
        import inspect
        source = inspect.getsource(mod)
        assert "stale_after_minutes" not in source
        assert "NO_DATA_NOTIFICATION_AFTER" in source


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_ids(component) -> list[str]:
    """Recursively collect all component IDs from a Dash layout."""
    ids = []
    if hasattr(component, "id") and component.id:
        ids.append(component.id)
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for child in children:
                ids.extend(_collect_ids(child))
        elif children is not None:
            ids.extend(_collect_ids(children))
    return ids
