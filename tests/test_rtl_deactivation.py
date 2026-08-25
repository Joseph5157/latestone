"""OPS-DEACT-1 RTL deactivation persistence tests — DEACT-D1..D7 frozen.

Pure classes cover vocabulary, strict-actor validation and the no-
activation-path contract. Database-backed suites run against the
module-scoped isolated_schema (tests/conftest.py), never the real
plant_monitoring tables.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from config import audit as audit_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import rtl_deactivation_service as deact


# ---------------------------------------------------------------------------
# Pure — vocabulary, actor validation, no-activation contract
# ---------------------------------------------------------------------------


class TestDeactivationVocabulary:
    def test_operation_fits_column_limit(self):
        assert len(audit_cfg.RTL_DEACTIVATED) <= 50

    def test_operation_name_is_exact(self):
        assert audit_cfg.RTL_DEACTIVATED == "RTL_DEACTIVATED"

    def test_audit_entity_is_the_stable_device_identity(self):
        """DEACT-D5: no active-state audit entity type is introduced."""
        assert audit_cfg.ENTITY_DEVICE == "device"

    def test_missing_actor_fails_before_any_database_access(self):
        with pytest.raises(deact.DeactivationError):
            deact.deactivate_rtl(device_id="any-d1", actor_user_id=None)

    def test_malformed_actor_fails_before_any_database_access(self):
        for bad in ("1", True, 4.0):
            with pytest.raises(deact.DeactivationError):
                deact.deactivate_rtl(device_id="any-d1", actor_user_id=bad)

    def test_no_activation_path_exists(self):
        """DEACT-D4: nothing in the repository or service may set
        is_active=true or emulate ingestion."""
        for module in (repo, deact):
            names = [n for n in dir(module) if not n.startswith("_")]
            assert not any(
                n.lower().startswith("activate") or "set_active" in n.lower()
                for n in names
            )
        # The only mutation exposed is a deactivation.
        assert callable(repo.deactivate_device_active_state)


# ---------------------------------------------------------------------------
# Database-backed — persisted behaviour on isolated schema
# ---------------------------------------------------------------------------

DEVICE_ID = "deact-p1-t1-d1"
TRANSFORMER_ID = "deact-p1-t1"


def _wipe() -> None:
    """Reset everything this module touches, FK-safe order."""
    with session_scope() as session:
        for table in (
            "audit_log", "rtl_active_state", "rtl_programming_requests",
            "message_forwarding", "user_device_assignments", "readings",
            "devices", "transformers", "plants", "users",
        ):
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.{table}"))


def _seed_hierarchy() -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants "
                "(plant_id, name, country, latitude, longitude) "
                "VALUES ('deact-p1', 'Deact Plant', 'Testland', 0, 0)"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES ('{TRANSFORMER_ID}', 'deact-p1', 't1')"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.devices "
                f"(device_id, transformer_id, device_code) "
                f"VALUES ('{DEVICE_ID}', '{TRANSFORMER_ID}', 'd1')"
            )
        )


def _make_active_row() -> dict:
    """Test fixture: an on-list device. Activation itself belongs to the
    future ingestion slice; tests may create this state directly."""
    with session_scope() as session:
        row = session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.rtl_active_state "
                f"(device_id, is_active, activated_at, updated_at) "
                f"VALUES (:device_id, TRUE, now(), now()) "
                f"RETURNING {repo._ACTIVE_STATE_COLUMNS}"
            ),
            {"device_id": DEVICE_ID},
        ).first()
    return {
        "is_active": bool(row[1]),
        "activated_at": row[2],
        "deactivated_at": row[3],
        "updated_at": row[4],
    }


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


def _assignment_count() -> int:
    with session_scope() as session:
        return session.execute(
            text(f"SELECT COUNT(*) FROM {repo._SCHEMA}.user_device_assignments")
        ).scalar_one()


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestDeactivationPersistence:
    def setup_method(self):
        _wipe()
        _seed_hierarchy()
        self.admin = repo.create_or_update_user(
            username="deact-admin", full_name="Deact Admin",
            role="administrator", status="active",
        ).user_id

    def test_active_row_transitions_exactly_once_to_false(self):
        before = _make_active_row()

        result = deact.deactivate_rtl(
            device_id=DEVICE_ID, actor_user_id=self.admin
        )

        assert result.outcome == deact.OUTCOME_DEACTIVATED
        after = _state_row()
        assert len(_audit_rows()) == 1          # exactly one transition+audit
        assert after["is_active"] is False
        assert after["activated_at"] == before["activated_at"]   # preserved
        assert after["updated_at"] > before["updated_at"]        # DB clock

    def test_deactivated_at_comes_from_the_database_clock(self):
        _make_active_row()
        result = deact.deactivate_rtl(
            device_id=DEVICE_ID, actor_user_id=self.admin
        )
        assert result.deactivated_at is not None
        assert _state_row()["deactivated_at"] == result.deactivated_at

    def test_absent_row_performs_zero_writes_and_zero_audits(self):
        """DEACT-D1: absence IS off-list; no inactive row manufactured."""
        result = deact.deactivate_rtl(
            device_id=DEVICE_ID, actor_user_id=self.admin
        )

        assert result.outcome == deact.OUTCOME_NOT_ON_ACTIVE_LIST
        assert _state_row() is None             # no insert
        assert _audit_rows() == []

    def test_already_false_row_performs_zero_writes_and_zero_audits(self):
        """DEACT-D2: idempotent re-application."""
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.rtl_active_state "
                    f"(device_id, is_active, deactivated_at, updated_at) "
                    f"VALUES (:d, FALSE, now(), now())"
                ),
                {"d": DEVICE_ID},
            )
        frozen = _state_row()

        result = deact.deactivate_rtl(
            device_id=DEVICE_ID, actor_user_id=self.admin
        )

        assert result.outcome == deact.OUTCOME_ALREADY_INACTIVE
        after = _state_row()
        assert after == frozen                  # zero churn, any column
        assert _audit_rows() == []

    def test_repeated_deactivation_does_not_churn_timestamps(self):
        _make_active_row()
        first = deact.deactivate_rtl(
            device_id=DEVICE_ID, actor_user_id=self.admin
        )
        frozen = _state_row()

        second = deact.deactivate_rtl(
            device_id=DEVICE_ID, actor_user_id=self.admin
        )

        assert second.outcome == deact.OUTCOME_ALREADY_INACTIVE
        assert _state_row() == frozen
        assert second.deactivated_at == first.deactivated_at

    def test_devices_status_is_untouched_by_deactivation(self):
        """DEACT-D6 / RTL-ACT-05: administrative status never merges with
        active-list state."""
        _make_active_row()
        status_before = _state_row()  # devices.status defaults to 'active'
        with session_scope() as session:
            device_status_before = session.execute(
                text(
                    f"SELECT status FROM {repo._SCHEMA}.devices "
                    f"WHERE device_id = :d"
                ),
                {"d": DEVICE_ID},
            ).scalar_one()

        deact.deactivate_rtl(device_id=DEVICE_ID, actor_user_id=self.admin)

        with session_scope() as session:
            device_status_after = session.execute(
                text(
                    f"SELECT status FROM {repo._SCHEMA}.devices "
                    f"WHERE device_id = :d"
                ),
                {"d": DEVICE_ID},
            ).scalar_one()
        assert device_status_before == device_status_after == "active"
        assert _state_row()["is_active"] is False
        assert status_before["is_active"] is True

    def test_assignments_are_untouched_by_deactivation(self):
        """DEACT-D6: an existing technician assignment survives."""
        _make_active_row()
        tech = repo.create_or_update_user(
            username="deact-tech", full_name="Deact Tech",
            role="technician", status="active",
        ).user_id
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.user_device_assignments "
                    "(device_id, user_id) VALUES (:d, :u)"
                ),
                {"d": DEVICE_ID, "u": tech},
            )
        assert _assignment_count() == 1

        deact.deactivate_rtl(device_id=DEVICE_ID, actor_user_id=self.admin)

        assert _assignment_count() == 1         # not ended, not deleted
        with session_scope() as session:
            ended_at = session.execute(
                text(
                    f"SELECT ended_at FROM {repo._SCHEMA}.user_device_assignments"
                )
            ).scalar_one()
        assert ended_at is None

    def test_monitoring_listing_is_unchanged_by_deactivation(self):
        """DEACT-D6: monitoring does not consume active-list state."""
        _make_active_row()
        listing_before = repo.list_all_devices()

        deact.deactivate_rtl(device_id=DEVICE_ID, actor_user_id=self.admin)

        listing_after = repo.list_all_devices()
        assert [(r.device_id, r.status) for r in listing_after] == [
            (r.device_id, r.status) for r in listing_before
        ]
        assert any(r.device_id == DEVICE_ID for r in listing_after)

    def test_read_back_survives_process_memory_from_postgresql(self):
        _make_active_row()
        deact.deactivate_rtl(device_id=DEVICE_ID, actor_user_id=self.admin)
        state = repo.get_device_active_state(DEVICE_ID)
        assert state is not None and state.is_active is False


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestDeactivationAudit:
    def setup_method(self):
        _wipe()
        _seed_hierarchy()
        self.admin = repo.create_or_update_user(
            username="deact-admin", full_name="Deact Admin",
            role="administrator", status="active",
        ).user_id

    def test_transition_audits_the_stable_device_identity_once(self):
        _make_active_row()

        deact.deactivate_rtl(device_id=DEVICE_ID, actor_user_id=self.admin)

        rows = _audit_rows()
        assert len(rows) == 1
        row = rows[0]
        assert row["operation"] == audit_cfg.RTL_DEACTIVATED
        assert row["entity_type"] == audit_cfg.ENTITY_DEVICE
        assert row["entity_id"] == DEVICE_ID
        assert row["user_id"] == self.admin     # strict D2 actor

    def test_payload_carries_previous_and_new_transition_state(self):
        """DEACT-D5: old_values/new_values carry previous/new is_active +
        deactivated_at; activated_at is untouched so it stays out."""
        fixture = _make_active_row()

        deact.deactivate_rtl(device_id=DEVICE_ID, actor_user_id=self.admin)

        row = _audit_rows()[0]
        assert set(row["old_values"].keys()) == {"is_active", "deactivated_at"}
        assert row["old_values"]["is_active"] is True
        assert row["old_values"]["deactivated_at"] is None
        assert set(row["new_values"].keys()) == {"is_active", "deactivated_at"}
        assert row["new_values"]["is_active"] is False
        assert row["new_values"]["deactivated_at"] is not None
        assert row["new_values"]["deactivated_at"] != fixture["deactivated_at"]

    def test_no_ops_never_write_audit_rows(self):
        """DEACT-D5: absent-row and already-inactive attempts audit nothing."""
        deact.deactivate_rtl(device_id=DEVICE_ID, actor_user_id=self.admin)
        assert _audit_rows() == []

        _make_active_row()
        deact.deactivate_rtl(device_id=DEVICE_ID, actor_user_id=self.admin)
        first = _audit_rows()
        assert len(first) == 1

        deact.deactivate_rtl(device_id=DEVICE_ID, actor_user_id=self.admin)
        assert _audit_rows() == first           # still exactly one

    def test_failed_audit_restores_the_entire_previous_active_row(
        self, monkeypatch
    ):
        """FWD-D5 atomicity: mutation + audit share one transaction. The
        same failure injection AUD-1 uses must leave the row exactly as it
        was — is_active, deactivated_at AND updated_at."""

        def explode(**kwargs):
            raise RuntimeError("simulated audit-store outage")

        monkeypatch.setattr(repo, "insert_audit_log", explode)
        fixture = _make_active_row()

        with pytest.raises(deact.DeactivationError):
            deact.deactivate_rtl(
                device_id=DEVICE_ID, actor_user_id=self.admin
            )

        restored = _state_row()
        assert restored["is_active"] is True
        assert restored["activated_at"] == fixture["activated_at"]
        assert restored["deactivated_at"] == fixture["deactivated_at"]
        assert restored["updated_at"] == fixture["updated_at"]
        assert _audit_rows() == []
