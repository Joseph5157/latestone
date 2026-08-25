"""AUD-1 audit wiring tests — atomicity, content, suppression rules.

Database-backed suites run against the module-scoped isolated_schema
(tests/conftest.py), never the real plant_monitoring tables. The pure-logic
class needs no database.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from config import audit as audit_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import audit_service
from services.device_registration import RegistrationError, register_device
from services.prototype_assignments import (
    assign_technician,
    unassign_technician,
)
from services.prototype_users import upsert_user


# ---------------------------------------------------------------------------
# Pure logic — vocabulary and payload hygiene
# ---------------------------------------------------------------------------


class TestAuditVocabulary:
    def test_operations_fit_column_limit(self):
        for name in (
            "DEVICE_REGISTERED",
            "DEVICE_ASSIGNED",
            "DEVICE_UNASSIGNED",
            "USER_CREATED",
            "USER_UPDATED",
        ):
            assert len(getattr(audit_cfg, name)) <= 50

    def test_entity_types_are_stable(self):
        assert audit_cfg.ENTITY_DEVICE == "device"
        assert audit_cfg.ENTITY_ASSIGNMENT == "device_assignment"
        assert audit_cfg.ENTITY_USER == "user"

    def test_record_requires_an_actor(self):
        # Strict D2: a missing/malformed actor fails BEFORE any DB access.
        with pytest.raises(audit_service.AuditError):
            audit_service.record(
                None,  # never touched — validation fails first
                operation=audit_cfg.DEVICE_REGISTERED,
                entity_type=audit_cfg.ENTITY_DEVICE,
                entity_id="d1",
                actor_user_id=None,
            )

    def test_sanitize_converts_datetimes(self):
        ts = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        out = audit_service._sanitize({"at": ts, "name": "x"})
        assert out == {"at": ts.isoformat(), "name": "x"}


# ---------------------------------------------------------------------------
# Database-backed wiring
# ---------------------------------------------------------------------------


def _seed_tree(plant_id="aud-p1", transformer_id="aud-p1-t1") -> str:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants "
                f"(plant_id, name, country, latitude, longitude) "
                f"VALUES (:plant_id, 'Audit Plant', 'Testland', 0, 0) "
                f"ON CONFLICT (plant_id) DO NOTHING"
            ),
            {"plant_id": plant_id},
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES (:tid, :plant_id, :tid) "
                f"ON CONFLICT (transformer_id) DO NOTHING"
            ),
            {"tid": transformer_id, "plant_id": plant_id},
        )
    return transformer_id


def _seed_device(device_id: str, transformer_id: str, code: str) -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.devices "
                f"(device_id, transformer_id, device_code) "
                f"VALUES (:device_id, :tid, :code)"
            ),
            {"device_id": device_id, "tid": transformer_id, "code": code},
        )


def _audit_rows(entity_type: str | None = None) -> list[dict]:
    with session_scope() as session:
        sql = (
            f"SELECT operation, entity_type, entity_id, old_values, "
            f"new_values, user_id FROM {repo._SCHEMA}.audit_log"
        )
        params: dict = {}
        if entity_type is not None:
            sql += " WHERE entity_type = :et"
            params["et"] = entity_type
        sql += " ORDER BY audit_id"
        rows = session.execute(text(sql), params).mappings().fetchall()
        return [dict(r) for r in rows]


def _wipe_transactional_tables() -> None:
    """Reset everything the audited flows touch, FK-safe order. The
    isolated schema is module-scoped, so classes share leftovers."""
    with session_scope() as session:
        for table in (
            "audit_log",
            "user_device_assignments",
            "devices",
            "transformers",
            "plants",
        ):
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.{table}"))


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestRegistrationAudit:
    def setup_method(self):
        _wipe_transactional_tables()
        self.admin_id = repo.create_or_update_user(
            username="aud-admin", full_name="aud-admin",
            role="administrator", status="active",
        ).user_id
        _seed_tree()

    def test_registration_writes_one_audit_row_with_new_values(self):
        device = register_device("aud-p1-t1", "29201", actor_user_id=self.admin_id)
        rows = _audit_rows(audit_cfg.ENTITY_DEVICE)
        assert len(rows) == 1
        row = rows[0]
        assert row["operation"] == audit_cfg.DEVICE_REGISTERED
        assert row["entity_id"] == device.device_id
        assert row["user_id"] == self.admin_id
        assert row["old_values"] is None
        assert row["new_values"] == {
            "device_id": device.device_id,
            "transformer_id": "aud-p1-t1",
            "device_code": "29201",
            "status": "active",
        }

    def test_failed_audit_rolls_back_the_registration(self, monkeypatch):
        def _explode(**kwargs):
            raise RuntimeError("simulated audit-store outage")

        monkeypatch.setattr(repo, "insert_audit_log", _explode)
        with pytest.raises(RegistrationError):
            register_device("aud-p1-t1", "29202", actor_user_id=self.admin_id)

        # THE key assertion: mutation + audit share one transaction, so the
        # device insert was rolled back together with the failed audit write.
        with session_scope() as session:
            count = session.execute(
                text(f"SELECT COUNT(*) FROM {repo._SCHEMA}.devices")
            ).scalar_one()
        assert count == 0
        assert _audit_rows() == []

    def test_unknown_actor_fails_the_operation_and_persists_nothing(self):
        with pytest.raises(RegistrationError):
            register_device("aud-p1-t1", "29203", actor_user_id=999999999)
        with session_scope() as session:
            count = session.execute(
                text(f"SELECT COUNT(*) FROM {repo._SCHEMA}.devices")
            ).scalar_one()
        assert count == 0


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestAssignmentAudit:
    def setup_method(self):
        _wipe_transactional_tables()
        self.admin_id = repo.create_or_update_user(
            username="aud-admin2", full_name="aud-admin2",
            role="administrator", status="active",
        ).user_id
        self.bob_id = repo.create_or_update_user(
            username="aud-bob", full_name="aud-bob",
            role="technician", status="active",
        ).user_id
        self.carol_id = repo.create_or_update_user(
            username="aud-carol", full_name="aud-carol",
            role="technician", status="active",
        ).user_id
        transformer = _seed_tree("aud-p2", "aud-p2-t1")
        _seed_device("aud-dev-1", transformer, "29211")

    def test_fresh_assignment_audits_null_old_and_full_new(self):
        assign_technician("aud-dev-1", "aud-bob", actor_user_id=self.admin_id)
        rows = [
            r for r in _audit_rows(audit_cfg.ENTITY_ASSIGNMENT)
            if r["entity_id"] == "aud-dev-1"
        ]
        assert len(rows) == 1
        row = rows[0]
        assert row["operation"] == audit_cfg.DEVICE_ASSIGNED
        assert row["old_values"] is None
        new = row["new_values"]
        assert new["technician_username"] == "aud-bob"
        assert new["technician_user_id"] == self.bob_id
        assert isinstance(new["assignment_id"], int)

    def test_reassignment_records_before_and_after_snapshots(self):
        assign_technician("aud-dev-1", "aud-bob", actor_user_id=self.admin_id)
        assign_technician("aud-dev-1", "aud-carol", actor_user_id=self.admin_id)
        rows = [
            r for r in _audit_rows(audit_cfg.ENTITY_ASSIGNMENT)
            if r["entity_id"] == "aud-dev-1"
            and r["operation"] == audit_cfg.DEVICE_ASSIGNED
        ]
        assert len(rows) == 2
        old = rows[1]["old_values"]
        new = rows[1]["new_values"]
        assert old["technician_username"] == "aud-bob"
        assert new["technician_username"] == "aud-carol"
        assert old["assignment_id"] != new["assignment_id"]
        # Stable stream: entity id is the device, not the assignment row.
        assert rows[0]["entity_id"] == rows[1]["entity_id"] == "aud-dev-1"

    def test_noop_reassignment_suppresses_audit_d1(self):
        assign_technician("aud-dev-1", "aud-bob", actor_user_id=self.admin_id)
        before = len(_audit_rows())
        assign_technician("aud-dev-1", "aud-bob", actor_user_id=self.admin_id)
        assert len(_audit_rows()) == before

    def test_unassign_audits_closed_row_with_null_new_values(self):
        assign_technician("aud-dev-1", "aud-bob", actor_user_id=self.admin_id)
        unassign_technician("aud-dev-1", actor_user_id=self.admin_id)
        rows = [
            r for r in _audit_rows(audit_cfg.ENTITY_ASSIGNMENT)
            if r["operation"] == audit_cfg.DEVICE_UNASSIGNED
        ]
        assert len(rows) == 1
        assert rows[0]["entity_id"] == "aud-dev-1"
        assert rows[0]["old_values"]["technician_username"] == "aud-bob"
        assert rows[0]["new_values"] is None

    def test_unassign_when_nothing_assigned_is_silent(self):
        unassign_technician("aud-dev-1", actor_user_id=self.admin_id)
        assert _audit_rows() == []


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestUserUpsertAudit:
    def setup_method(self):
        _wipe_transactional_tables()
        self.admin_id = repo.create_or_update_user(
            username="aud-admin3", full_name="aud-admin3",
            role="administrator", status="active",
        ).user_id

    def _rows(self):
        return _audit_rows(audit_cfg.ENTITY_USER)

    def test_create_then_update_audits_both_with_real_diff(self):
        upsert_user("aud-new", "n@example.com", "general", "active",
                    actor_user_id=self.admin_id)
        created = self._rows()
        assert len(created) == 1
        assert created[0]["operation"] == audit_cfg.USER_CREATED
        assert created[0]["old_values"] is None
        assert created[0]["new_values"]["username"] == "aud-new"

        user_id = int(created[0]["entity_id"])
        upsert_user("aud-new", "n@example.com", "technician", "active",
                    actor_user_id=self.admin_id)
        updated = self._rows()
        assert len(updated) == 2
        row = updated[1]
        assert row["operation"] == audit_cfg.USER_UPDATED
        assert int(row["entity_id"]) == user_id  # stable identity
        assert row["old_values"]["role"] == "general"
        assert row["new_values"]["role"] == "technician"
