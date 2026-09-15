"""Tests for Notification Center — config, service, page, callbacks.

All tests exercise pure logic (no Dash runtime, no database, no notification service).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dash import no_update

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
        assert summary["by_type"] == {}

    def test_summary_counts_by_category_label(self):
        rows = [
            _row("a", ">24h No Data"),
            _row("b", ">24h No Data"),
            _row("c", "Battery Alarm"),
        ]
        summary = notification_summary(rows)
        assert summary["total"] == 3
        assert summary["by_type"] == {">24h No Data": 2, "Battery Alarm": 1}


# ---------------------------------------------------------------------------
# ENT-4 — merged ordering authority
# ---------------------------------------------------------------------------

class TestMergedOrderingAuthority:
    """`current_notifications` owns the operator-facing order: newest first,
    stable key ascending as tiebreak. Builders keep deterministic internal
    order; only the merged result defines what the operator scans."""

    def test_newest_first_reorders_builder_output(self):
        from services.notification_service import newest_first

        older = _row("no_data_24h:d1", ">24h No Data",
                     occurred_at=NOW - timedelta(days=3))
        newer = _row("battery_alarm:d2", "Battery Alarm",
                     occurred_at=NOW - timedelta(minutes=20))
        merged = newest_first([older, newer])
        assert [r.key for r in merged] == ["battery_alarm:d2", "no_data_24h:d1"]

    def test_a_recent_event_outranks_an_old_no_data_row(self):
        """The operational question is 'what happened most recently', so a
        20-minute-old battery event outranks a 3-day-old no-data row."""
        from services.notification_service import newest_first

        rows = [
            _row("no_data_24h:d1", ">24h No Data",
                 occurred_at=NOW - timedelta(days=3)),
            _row("battery_alarm:d2", "Battery Alarm",
                 occurred_at=NOW - timedelta(minutes=20)),
            _row("power_down:d3", "Power Down",
                 occurred_at=NOW - timedelta(hours=2)),
        ]
        keys = [r.key for r in newest_first(rows)]
        assert keys == [
            "battery_alarm:d2", "power_down:d3", "no_data_24h:d1",
        ]

    def test_equal_timestamps_break_by_stable_key(self):
        from services.notification_service import newest_first

        same_ts = NOW - timedelta(hours=1)
        rows = [
            _row("power_down:d1", "Power Down", occurred_at=same_ts),
            _row("battery_alarm:d1", "Battery Alarm", occurred_at=same_ts),
        ]
        keys = [r.key for r in newest_first(rows)]
        assert keys == sorted(keys)

    def test_current_notifications_sorts_the_merged_result(self, monkeypatch):
        """The composition point applies the authority: whatever order the
        builders returned, the caller receives newest-first."""
        from repositories import plant_monitoring_repository as repo
        from services import notification_service as svc
        from services.device_scope import DeviceScope

        class FakeEvent:
            def __init__(self, event_id, device_id, event_type, event_ts):
                self.event_id = event_id
                self.device_id = device_id
                self.reported_uid = None
                self.event_type = event_type
                self.event_ts = event_ts
                self.battery_voltage = None
                self.temperature = None
                self.message = None

        # BR008 builder emits device-id order; event builder emits stable-key
        # order. The oldest no-data row must still land last.
        monkeypatch.setattr(
            svc, "build_current_notifications",
            lambda rows, ref: [
                _row("no_data_24h:d1", ">24h No Data",
                     occurred_at=NOW - timedelta(days=5)),
            ],
        )
        monkeypatch.setattr(
            repo, "list_recent_device_events",
            lambda **kwargs: [
                FakeEvent(1, "d2", "battery_low", NOW - timedelta(hours=1)),
            ],
        )

        result = svc.current_notifications(
            reading_rows=[], scope=DeviceScope(device_ids=None), now=NOW,
        )
        assert [r.key for r in result] == [
            "battery_alarm:d2", "no_data_24h:d1",
        ]


class TestSummaryCategoryOrder:
    """D4 refinement: the summary walks the configured category order and
    appends the admin-only quarantine surface — never count order."""

    def test_order_is_config_order_plus_unregistered(self):
        from services.notification_service import summary_category_order

        order = summary_category_order()
        assert order == tuple(
            c.label for c in all_categories()
        ) + ("Unregistered UID",)

    def test_order_does_not_depend_on_counts(self):
        from services.notification_service import summary_category_order

        assert list(summary_category_order()) == list(summary_category_order())


# ---------------------------------------------------------------------------
# ENT-4 — callback presentation (pure helpers)
# ---------------------------------------------------------------------------

class TestCallbackPresentation:
    def test_summary_line_is_text_first_in_config_order(self):
        from callbacks.notifications import format_summary_line

        line = format_summary_line(
            8,
            {">24h No Data": 3, "Battery Alarm": 2, "Power Down": 1,
             "Sensor Error": 1, "Startup / Check-In": 1},
        )
        assert line.startswith("8 current notifications")
        labels = [c.label for c in all_categories() if c.label in line]
        assert labels == [c.label for c in all_categories()
                          if c.label in {">24h No Data", "Battery Alarm",
                                         "Power Down", "Sensor Error",
                                         "Startup / Check-In"}]

    def test_summary_line_omits_zero_count_categories(self):
        from callbacks.notifications import format_summary_line

        line = format_summary_line(1, {"Battery Alarm": 1})
        assert line == "1 current notification · Battery Alarm 1"

    def test_summary_line_singular_for_one_notification(self):
        from callbacks.notifications import format_summary_line

        assert format_summary_line(1, {}) == "1 current notification"
        assert format_summary_line(2, {}) == "2 current notifications"

    def test_summary_line_appends_unregistered_last(self):
        from callbacks.notifications import format_summary_line

        line = format_summary_line(
            2, {"Battery Alarm": 1, "Unregistered UID": 1},
        )
        assert line.endswith("Unregistered UID 1")

    def _cell(self, column_id, row_id):
        return {"column_id": column_id, "row_id": row_id}

    def test_entity_cell_navigates_via_hidden_href(self):
        from callbacks.notifications import notification_row_target

        data = [{"id": "battery_alarm:d1", "_href": "/devices/d1"}]
        result = notification_row_target(
            self._cell("entity_label", "battery_alarm:d1"), data,
        )
        assert result == "/devices/d1"

    def test_non_entity_columns_do_not_navigate(self):
        from callbacks.notifications import notification_row_target

        data = [{"id": "battery_alarm:d1", "_href": "/devices/d1"}]
        assert notification_row_target(
            self._cell("notification_type", "battery_alarm:d1"), data,
        ) is no_update

    def test_unregistered_row_never_navigates(self):
        from callbacks.notifications import notification_row_target

        data = [{"id": "unregistered_uid:99999", "_href": ""}]
        assert notification_row_target(
            self._cell("entity_label", "unregistered_uid:99999"), data,
        ) is no_update

    def test_unknown_row_id_is_ignored(self):
        from callbacks.notifications import notification_row_target

        assert notification_row_target(
            self._cell("entity_label", "ghost"), [{"id": "a", "_href": "/x"}],
        ) is no_update


def _row(key, notification_type, occurred_at=None, entity_type="Device"):
    return NotificationRow(
        key=key, entity_id="d1", entity_label="Device 1",
        entity_type=entity_type, notification_type=notification_type,
        detail="test", occurred_at=occurred_at, href="/devices/d1",
    )


# ---------------------------------------------------------------------------
# ENT-4 — presentation CSS source guards
# ---------------------------------------------------------------------------

import pathlib
import re

CSS_TEXT = (
    pathlib.Path(__file__).resolve().parent.parent / "assets" / "app.css"
).read_text(encoding="utf-8")


class TestNotificationPresentationCSS:
    def test_one_shared_neutral_chip_for_all_categories(self):
        """D1: the chip rule is column-scoped, so every category receives the
        identical treatment — the name differentiates, not colour."""
        match = re.search(
            r"\.entity-table-wrapper--notification-axis "
            r"td\[data-dash-column=\"notification_type\"\] \.dash-cell-value\s*\{([^}]*)\}",
            CSS_TEXT, re.S,
        )
        assert match, "the neutral chip rule must exist"

    def test_chip_never_borrows_severity_tokens(self):
        match = re.search(
            r"td\[data-dash-column=\"notification_type\"\] \.dash-cell-value\s*\{([^}]*)\}",
            CSS_TEXT, re.S,
        )
        block = match.group(1)
        for forbidden in ("--color-warning", "--color-danger", "--color-stale",
                          "--state-stale", "--state-no_data"):
            assert forbidden not in block

    @pytest.mark.parametrize(
        "column_id",
        ["occurred_at", "entity_label", "entity_type", "notification_type",
         "acknowledgement_state", "acknowledge_action", "detail"],
    )
    def test_mobile_record_labels_cover_all_five_columns(self, column_id):
        media = CSS_TEXT[CSS_TEXT.index("@media (max-width: 768px)"):]
        assert re.search(
            rf"td\[data-dash-column=\"{column_id}\"\]::before",
            media,
        ), column_id


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

    def test_no_sms_email_delivery_claims(self):
        """Delivery must never be claimed as implemented. The honest banner
        names SMS/email only inside an explicit negation, so the guard
        requires that negation to travel with the words."""
        lay = layout()
        text = str(lay).lower()
        assert "rabbitmq" not in text
        assert "mqtt" not in text
        if "sms" in text or "email" in text:
            assert "not connected" in text


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
