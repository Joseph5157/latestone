"""Database-backed acknowledgement persistence, scope, and audit tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from config import audit as audit_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import alarm_acknowledgement_service as service
from services.device_scope import DeviceScope


NOW = datetime(2026, 9, 15, 10, 30, tzinfo=timezone.utc)


def _wipe() -> None:
    with session_scope() as session:
        for table in ("audit_log", "device_events", "user_device_assignments", "devices", "transformers", "plants", "users"):
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.{table}"))


def _seed() -> tuple[int, int]:
    with session_scope() as session:
        session.execute(text(f"INSERT INTO {repo._SCHEMA}.plants (plant_id, name, country, latitude, longitude) VALUES ('ack-p1', 'Ack Plant', 'Testland', 0, 0)"))
        session.execute(text(f"INSERT INTO {repo._SCHEMA}.transformers (transformer_id, plant_id, transformer_code) VALUES ('ack-p1-t1', 'ack-p1', 't1')"))
        for device_id in ("ack-d1", "ack-d2"):
            session.execute(text(f"INSERT INTO {repo._SCHEMA}.devices (device_id, transformer_id, device_code) VALUES (:device_id, 'ack-p1-t1', :device_id)"), {"device_id": device_id})
    admin = repo.create_or_update_user(username="ack-admin", full_name="Ack Admin", role="administrator", status="active").user_id
    technician = repo.create_or_update_user(username="ack-tech", full_name="Ack Tech", role="technician", status="active").user_id
    return admin, technician


def _event(device_id: str, event_type: str = "battery_low") -> int:
    return repo.insert_device_event(event_type=event_type, event_ts=NOW, device_id=device_id, source="test")


def _audit_rows() -> list[dict]:
    with session_scope() as session:
        rows = session.execute(text(f"SELECT operation, entity_id, user_id, old_values, new_values FROM {repo._SCHEMA}.audit_log ORDER BY audit_id")).mappings().all()
    return [dict(row) for row in rows]


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestAlarmAcknowledgementPersistence:
    def setup_method(self):
        _wipe()
        self.admin_id, self.technician_id = _seed()

    def test_persists_actor_time_and_audit_atomically(self):
        event_id = _event("ack-d1")
        result = service.acknowledge_alarm(event_id=event_id, actor_user_id=self.admin_id, scope=DeviceScope(None))
        assert result.changed is True
        event = repo.get_device_event(event_id)
        assert event["acknowledged_by_user_id"] == self.admin_id
        assert event["acknowledged_at"] is not None
        assert _audit_rows() == [{
            "operation": audit_cfg.ALARM_ACKNOWLEDGED,
            "entity_id": "ack-d1",
            "user_id": self.admin_id,
            "old_values": {"event_id": event_id, "acknowledged_at": None},
            "new_values": {
                "event_id": event_id,
                "acknowledged_at": event["acknowledged_at"].isoformat(),
                "acknowledged_by_user_id": self.admin_id,
            },
        }]

    def test_acknowledgement_is_idempotent_and_does_not_clear_event(self):
        event_id = _event("ack-d1")
        assert service.acknowledge_alarm(event_id=event_id, actor_user_id=self.admin_id, scope=DeviceScope(None)).changed
        assert not service.acknowledge_alarm(event_id=event_id, actor_user_id=self.admin_id, scope=DeviceScope(None)).changed
        assert repo.get_device_event(event_id)["event_type"] == "battery_low"
        assert len(_audit_rows()) == 1

    def test_technician_can_acknowledge_assigned_device_only(self):
        event_id = _event("ack-d1")
        result = service.acknowledge_alarm(event_id=event_id, actor_user_id=self.technician_id, scope=DeviceScope(frozenset({"ack-d1"})))
        assert result.changed

    def test_scope_blocks_unassigned_event_without_persistence_or_audit(self):
        event_id = _event("ack-d2")
        with pytest.raises(service.AlarmAcknowledgementError):
            service.acknowledge_alarm(event_id=event_id, actor_user_id=self.technician_id, scope=DeviceScope(frozenset({"ack-d1"})))
        event = repo.get_device_event(event_id)
        assert event["acknowledged_at"] is None
        assert _audit_rows() == []

    def test_non_alarm_event_is_not_acknowledgeable(self):
        event_id = _event("ack-d1", "startup")
        with pytest.raises(service.AlarmAcknowledgementError):
            service.acknowledge_alarm(event_id=event_id, actor_user_id=self.admin_id, scope=DeviceScope(None))
        assert repo.get_device_event(event_id)["acknowledged_at"] is None
