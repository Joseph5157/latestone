"""INGEST-1I RTL activation persistence tests — ACT-D3/D4 frozen semantics.

Covers repo.activate_device_active_state directly (the deactivation mirror)
and the system-originated RTL_ACTIVATED audit row. End-to-end ingestion
behaviour lives in test_device_event_ingestion_db.py.

Database-backed suites run against the module-scoped isolated_schema
(tests/conftest.py), never the real plant_monitoring tables.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from config import audit as audit_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import audit_service


DEVICE_ID = "act-p1-t1-d1"
TRANSFORMER_ID = "act-p1-t1"


def _wipe() -> None:
    with session_scope() as session:
        for table in (
            "audit_log", "device_events", "rtl_active_state",
            "rtl_programming_requests", "message_forwarding",
            "user_device_assignments", "readings",
            "devices", "transformers", "plants", "users",
        ):
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.{table}"))


def _seed_hierarchy() -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants "
                "(plant_id, name, country, latitude, longitude) "
                "VALUES ('act-p1', 'Act Plant', 'Testland', 0, 0)"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES ('{TRANSFORMER_ID}', 'act-p1', 't1')"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.devices "
                f"(device_id, transformer_id, device_code) "
                f"VALUES ('{DEVICE_ID}', '{TRANSFORMER_ID}', '29001')"
            )
        )


def _state_row() -> dict | None:
    with session_scope() as session:
        row = session.execute(
            text(
                f"SELECT {repo._ACTIVE_STATE_COLUMNS} "
                f"FROM {repo._SCHEMA}.rtl_active_state WHERE device_id = :d"
            ),
            {"d": DEVICE_ID},
        ).first()
    if row is None:
        return None
    return {
        "device_id": row[0],
        "is_active": bool(row[1]),
        "activated_at": row[2],
        "deactivated_at": row[3],
        "updated_at": row[4],
    }


def _make_inactive_row() -> dict:
    """A previously-activated-then-deactivated device."""
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.rtl_active_state "
                f"(device_id, is_active, deactivated_at, updated_at) "
                f"VALUES (:d, FALSE, now(), now())"
            ),
            {"d": DEVICE_ID},
        )
    return _state_row()


def _make_active_row() -> dict:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.rtl_active_state "
                f"(device_id, is_active, activated_at, updated_at) "
                f"VALUES (:d, TRUE, now(), now())"
            ),
            {"d": DEVICE_ID},
        )
    return _state_row()


def _deactivate_via_service() -> None:
    """Use the REAL deactivation path to build inactive state."""
    admin = repo.create_or_update_user(
        username="act-admin", full_name="Act Admin",
        role="administrator", status="active",
    ).user_id
    from services.rtl_deactivation_service import deactivate_rtl

    deactivate_rtl(device_id=DEVICE_ID, actor_user_id=admin)


def _audit_rows() -> list[dict]:
    with session_scope() as session:
        rows = session.execute(
            text(
                f"SELECT operation, entity_type, entity_id, old_values, "
                f"new_values, user_id FROM {repo._SCHEMA}.audit_log "
                f"ORDER BY audit_id"
            )
        ).mappings().fetchall()
    return [dict(r) for r in rows]


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestActivationTransitions:
    def setup_method(self):
        _wipe()
        _seed_hierarchy()

    def test_absent_row_first_activation_inserts_active(self):
        """ACT-D4: absent → active. Absence here means never-seen, so the
        row IS inserted (unlike deactivation, where absence means off-list)."""
        change = repo.activate_device_active_state(DEVICE_ID)

        assert change.changed is True
        assert change.previous is None
        after = _state_row()
        assert after["is_active"] is True
        assert after["activated_at"] is not None   # DB clock
        assert after["deactivated_at"] is None
        # activated_at and updated_at come from the same now():
        assert after["updated_at"] == after["activated_at"]

    def test_inactive_row_reactivates_preserving_deactivated_at(self):
        """ACT-D4: inactive → active refreshes activated_at/updated_at from
        the DB clock; prior deactivated_at survives untouched."""
        fixture = _make_inactive_row()
        assert fixture["is_active"] is False

        change = repo.activate_device_active_state(DEVICE_ID)

        assert change.changed is True
        after = _state_row()
        assert after["is_active"] is True
        assert after["deactivated_at"] == fixture["deactivated_at"]
        assert after["updated_at"] > fixture["updated_at"]

    def test_active_row_is_an_idempotent_no_op(self):
        """ACT-D3: active → active churns nothing at all."""
        fixture = _make_active_row()

        change = repo.activate_device_active_state(DEVICE_ID)

        assert change.changed is False
        assert change.previous == change.current
        assert _state_row() == fixture             # zero churn, any column

    def test_full_lifecycle_through_real_transitions(self):
        """absent→active→inactive→active with the real service paths;
        timestamps behave as last-TRANSITION markers throughout."""
        first = repo.activate_device_active_state(DEVICE_ID)
        activated_1 = _state_row()["activated_at"]

        _deactivate_via_service()
        deactivated = _state_row()
        assert deactivated["is_active"] is False
        assert deactivated["activated_at"] == activated_1  # preserved

        second = repo.activate_device_active_state(DEVICE_ID)
        reactivated = _state_row()
        assert second.changed is True
        assert reactivated["is_active"] is True
        assert reactivated["activated_at"] > activated_1   # refreshed
        assert reactivated["deactivated_at"] == deactivated["deactivated_at"]

        third = repo.activate_device_active_state(DEVICE_ID)
        assert third.changed is False              # ACT-D3 no-op


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestSystemOriginatedAudit:
    def setup_method(self):
        _wipe()
        _seed_hierarchy()

    def test_system_originated_record_persists_null_actor(self):
        """ACT-D5 / INGEST-D6: allowlisted op + explicit flag → user_id NULL.
        No synthetic system user exists."""
        with session_scope() as session:
            audit_service.record(
                session,
                operation=audit_cfg.RTL_ACTIVATED,
                entity_type=audit_cfg.ENTITY_DEVICE,
                entity_id=DEVICE_ID,
                old_values={"is_active": None},
                new_values={"is_active": True},
                actor_user_id=None,
                system_originated=True,
            )

        row = _audit_rows()[0]
        assert row["operation"] == audit_cfg.RTL_ACTIVATED
        assert row["user_id"] is None
        assert row["entity_type"] == "device"
        assert row["entity_id"] == DEVICE_ID
