"""Pure acknowledgement policy, projection, and Notification Center UI tests."""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from callbacks.notifications import ACKNOWLEDGE_COLUMN, notification_columns_and_rows
from services.action_guard import may_action
from services.auth_service import AuthenticatedUser
from services.authorization import ACKNOWLEDGE_ALARM
from services.device_scope import DeviceScope
from services.event_semantics import build_event_notifications
from services.notification_service import NotificationRow
from services import alarm_acknowledgement_service


NOW = datetime(2026, 9, 15, 10, 30, tzinfo=timezone.utc)


def _user(role: str) -> AuthenticatedUser:
    return AuthenticatedUser(user_id=7, username="operator", full_name="Operator", role=role)


def _alarm(device_id: str, *, event_id: int = 11, acknowledged_at=None) -> NotificationRow:
    return NotificationRow(
        key=f"battery_alarm:{device_id}",
        entity_id=device_id,
        entity_label=device_id,
        entity_type="Device",
        notification_type="Battery Alarm",
        detail="1 event(s); latest 2026-09-15 10:30 UTC",
        occurred_at=NOW,
        href=f"/devices/{device_id}",
        event_id=event_id,
        acknowledgement_state="Acknowledged" if acknowledged_at else "Active",
        acknowledged_at=acknowledged_at,
    )


class TestAcknowledgementActionPolicy:
    def test_administrator_may_acknowledge_any_device(self):
        assert may_action(
            _user("administrator"), ACKNOWLEDGE_ALARM,
            device_id="d-other", scope=DeviceScope(frozenset({"d1"})),
        )

    def test_technician_may_acknowledge_only_assigned_device(self):
        scope = DeviceScope(frozenset({"d1"}))
        assert may_action(_user("technician"), ACKNOWLEDGE_ALARM, device_id="d1", scope=scope)
        assert not may_action(_user("technician"), ACKNOWLEDGE_ALARM, device_id="d2", scope=scope)

    def test_general_is_never_authorised_even_with_unrestricted_visibility(self):
        assert not may_action(
            _user("general"), ACKNOWLEDGE_ALARM,
            device_id="d1", scope=DeviceScope(None),
        )


class TestNotificationAcknowledgementPresentation:
    def test_administrator_sees_active_alarm_action(self):
        columns, rows = notification_columns_and_rows(
            [_alarm("d1")], _user("administrator"), DeviceScope(None),
        )
        assert ACKNOWLEDGE_COLUMN in {column["id"] for column in columns}
        assert rows[0][ACKNOWLEDGE_COLUMN] == "Acknowledge"
        assert rows[0]["acknowledgement_state"] == "Active"

    def test_technician_cannot_receive_action_for_unassigned_alarm(self):
        columns, rows = notification_columns_and_rows(
            [_alarm("d2")], _user("technician"), DeviceScope(frozenset({"d1"})),
        )
        assert ACKNOWLEDGE_COLUMN not in {column["id"] for column in columns}
        assert rows[0][ACKNOWLEDGE_COLUMN] == ""

    def test_general_has_no_acknowledgement_action_column(self):
        columns, rows = notification_columns_and_rows(
            [_alarm("d1")], _user("general"), DeviceScope(None),
        )
        assert ACKNOWLEDGE_COLUMN not in {column["id"] for column in columns}
        assert rows[0][ACKNOWLEDGE_COLUMN] == ""

    def test_acknowledged_alarm_is_visible_without_action_and_keeps_timestamp(self):
        columns, rows = notification_columns_and_rows(
            [_alarm("d1", acknowledged_at=NOW)], _user("administrator"), DeviceScope(None),
        )
        assert ACKNOWLEDGE_COLUMN not in {column["id"] for column in columns}
        assert rows[0][ACKNOWLEDGE_COLUMN] == ""
        assert rows[0]["acknowledgement_state"].startswith("Acknowledged · 2026-09-15")

    def test_freshness_notification_has_no_acknowledgement_action(self):
        no_data = NotificationRow(
            key="no_data_24h:d1", entity_id="d1", entity_label="d1",
            entity_type="Device", notification_type=">24h No Data",
            detail="Last reading", occurred_at=NOW, href="/devices/d1",
        )
        columns, rows = notification_columns_and_rows(
            [no_data], _user("administrator"), DeviceScope(None),
        )
        assert ACKNOWLEDGE_COLUMN not in {column["id"] for column in columns}
        assert rows[0]["acknowledgement_state"] == "—"


class TestEventProjection:
    def test_latest_alarm_carries_active_state_and_event_id(self):
        event = SimpleNamespace(
            event_id=21, device_id="d1", transformer_id="t1", reported_uid=None,
            event_type="battery_low", event_ts=NOW, battery_voltage=3.4,
            acknowledged_at=None,
        )
        row = build_event_notifications([event])[0]
        assert row.event_id == 21
        assert row.acknowledgement_state == "Active"

    def test_latest_acknowledged_alarm_remains_visible_and_is_not_cleared(self):
        event = SimpleNamespace(
            event_id=22, device_id="d1", transformer_id="t1", reported_uid=None,
            event_type="battery_low", event_ts=NOW, battery_voltage=None,
            acknowledged_at=NOW,
        )
        row = build_event_notifications([event])[0]
        assert row.event_id == 22
        assert row.acknowledgement_state == "Acknowledged"
        assert row.acknowledged_at == NOW


def test_callback_uses_trusted_identity_scope_and_action_guard():
    source = __import__("inspect").getsource(__import__("callbacks.notifications", fromlist=["*"]))
    assert "current_identity()" in source
    assert "current_device_scope()" in source
    assert "require_action(user, ACKNOWLEDGE_ALARM" in source
    assert "auth_data.get" not in source


def test_service_writes_acknowledgement_and_audit_in_one_flow(monkeypatch):
    event_data = {
        "event_id": 41, "device_id": "d1", "transformer_id": "t1",
        "reported_uid": None, "event_type": "battery_low", "severity": None,
        "event_ts": NOW, "temperature": None, "battery_voltage": None,
        "message": None, "source": "test", "created_at": NOW,
        "acknowledged_at": None, "acknowledged_by_user_id": None,
    }
    updated = SimpleNamespace(
        event_id=41, device_id="d1", acknowledged_at=NOW,
    )
    calls = []
    monkeypatch.setattr(alarm_acknowledgement_service, "session_scope", lambda: nullcontext(object()))
    monkeypatch.setattr(alarm_acknowledgement_service.repo, "get_device_event", lambda *args, **kwargs: event_data)
    monkeypatch.setattr(alarm_acknowledgement_service.repo, "acknowledge_device_event", lambda *args, **kwargs: updated)
    monkeypatch.setattr(alarm_acknowledgement_service.audit_service, "record", lambda *args, **kwargs: calls.append(kwargs))

    result = alarm_acknowledgement_service.acknowledge_alarm(
        event_id=41, actor_user_id=7, scope=DeviceScope(frozenset({"d1"})),
    )
    assert result.changed
    assert calls[0]["operation"] == "ALARM_ACKNOWLEDGED"
    assert calls[0]["actor_user_id"] == 7
