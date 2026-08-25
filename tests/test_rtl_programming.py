"""OPS-PROG-1 RTL programming persistence tests — PROG-D1..D7 frozen.

Pure classes cover vocabulary, strict-actor validation and MSISDN
validation. Database-backed suites run against the module-scoped
isolated_schema (tests/conftest.py), never the real plant_monitoring
tables.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from config import audit as audit_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import rtl_programming_service as prog


# ---------------------------------------------------------------------------
# Pure — vocabulary, actor and MSISDN validation
# ---------------------------------------------------------------------------


class TestProgrammingVocabulary:
    def test_operation_fits_column_limit(self):
        assert len(audit_cfg.RTL_PROGRAM_REQUESTED) <= 50

    def test_operation_name_is_exact(self):
        assert audit_cfg.RTL_PROGRAM_REQUESTED == "RTL_PROGRAM_REQUESTED"

    def test_audit_entity_is_the_stable_device_identity(self):
        """PROG-D5: no programming-request entity type is introduced."""
        assert audit_cfg.ENTITY_DEVICE == "device"

    def test_request_method_is_dashboard(self):
        """PROG-D2: nothing was sent, so never 'sms'."""
        assert prog.REQUEST_METHOD_DASHBOARD == "dashboard"

    def test_missing_actor_fails_before_any_database_access(self):
        with pytest.raises(prog.ProgrammingError):
            prog.record_request(
                device_id="any-d1", master_msisdn="0700000000",
                actor_user_id=None,
            )

    def test_malformed_actor_fails_before_any_database_access(self):
        for bad in ("1", True, 4.0):
            with pytest.raises(prog.ProgrammingError):
                prog.record_request(
                    device_id="any-d1", master_msisdn="0700000000",
                    actor_user_id=bad,
                )


class TestMasterMsisdnValidation:
    """PROG-D1: manual entry only; trim; non-empty; schema limit of 20.
    No telephone-format invention."""

    def test_non_string_rejected(self):
        with pytest.raises(prog.ProgrammingError):
            prog._validate_master_msisdn(700000000)

    def test_empty_rejected(self):
        with pytest.raises(prog.ProgrammingError):
            prog._validate_master_msisdn("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(prog.ProgrammingError):
            prog._validate_master_msisdn("   ")

    def test_surrounding_whitespace_is_trimmed(self):
        assert prog._validate_master_msisdn("  0700000000  ") == "0700000000"

    def test_twenty_characters_accepted(self):
        assert len(prog._validate_master_msisdn("1" * 20)) == 20

    def test_over_twenty_characters_rejected(self):
        with pytest.raises(prog.ProgrammingError):
            prog._validate_master_msisdn("1" * 21)


# ---------------------------------------------------------------------------
# Database-backed — persisted behaviour on isolated schema
# ---------------------------------------------------------------------------

DEVICE_ID = "prog-p1-t1-d1"
TRANSFORMER_ID = "prog-p1-t1"


def _wipe() -> None:
    """Reset everything this module touches, FK-safe order."""
    with session_scope() as session:
        for table in (
            "audit_log", "rtl_programming_requests", "message_forwarding",
            "user_device_assignments", "readings", "devices",
            "transformers", "plants", "users",
        ):
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.{table}"))


def _seed_hierarchy() -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants "
                "(plant_id, name, country, latitude, longitude) "
                "VALUES ('prog-p1', 'Prog Plant', 'Testland', 0, 0)"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES ('{TRANSFORMER_ID}', 'prog-p1', 't1')"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.devices "
                f"(device_id, transformer_id, device_code) "
                f"VALUES ('{DEVICE_ID}', '{TRANSFORMER_ID}', 'd1')"
            )
        )


def _request_rows() -> list[dict]:
    with session_scope() as session:
        rows = session.execute(
            text(
                f"SELECT request_id, device_id, transformer_id, requested_by, "
                f"master_msisdn, requested_at, request_method, status, "
                f"completed_at, error_message "
                f"FROM {repo._SCHEMA}.rtl_programming_requests ORDER BY request_id"
            )
        ).mappings().fetchall()
    return [dict(r) for r in rows]


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
class TestProgrammingRequestPersistence:
    def setup_method(self):
        _wipe()
        _seed_hierarchy()
        self.admin = repo.create_or_update_user(
            username="prog-admin", full_name="Prog Admin",
            role="administrator", status="active",
        ).user_id

    def _record(self, msisdn="0700000000", device_id=DEVICE_ID):
        return prog.record_request(
            device_id=device_id, master_msisdn=msisdn,
            actor_user_id=self.admin,
        )

    def test_valid_submission_inserts_exactly_one_row_and_one_audit(self):
        record = self._record()

        rows = _request_rows()
        audits = _audit_rows()
        assert len(rows) == 1
        assert len(audits) == 1
        assert rows[0]["request_id"] == record.request_id

    def test_requested_by_is_the_acting_session_identity(self):
        record = self._record()
        assert record.requested_by == self.admin
        assert _request_rows()[0]["requested_by"] == self.admin

    def test_device_id_persisted_exactly(self):
        assert self._record().device_id == DEVICE_ID

    def test_transformer_id_is_point_in_time_snapshot(self):
        """The row carries the device's transformer at request time —
        stored in the row, not re-derived at read time."""
        record = self._record()
        assert record.transformer_id == TRANSFORMER_ID
        assert _request_rows()[0]["transformer_id"] == TRANSFORMER_ID

    def test_manually_entered_msisdn_persists_exactly(self):
        record = self._record(msisdn="27821234567")
        assert record.master_msisdn == "27821234567"
        assert _request_rows()[0]["master_msisdn"] == "27821234567"

    def test_whitespace_around_msisdn_is_trimmed_before_persisting(self):
        record = self._record(msisdn="   0700000000\t")
        assert record.master_msisdn == "0700000000"

    def test_row_stays_pending_with_null_completion_columns(self):
        """PROG-D6: this slice creates requests only."""
        self._record()

        row = _request_rows()[0]
        assert row["status"] == "pending"
        assert row["completed_at"] is None
        assert row["error_message"] is None

    def test_requested_at_comes_from_the_database_clock(self):
        record = self._record()
        assert record.requested_at is not None

    def test_unknown_device_records_nothing(self):
        with pytest.raises(prog.ProgrammingError):
            self._record(device_id="nope-t9-d9")

        assert _request_rows() == []
        assert _audit_rows() == []

    def test_empty_msisdn_rejected_with_zero_rows_and_zero_audits(self):
        for bad in ("", "   "):
            with pytest.raises(prog.ProgrammingError):
                self._record(msisdn=bad)

        assert _request_rows() == []
        assert _audit_rows() == []

    def test_overlong_msisdn_rejected_with_zero_rows_and_zero_audits(self):
        with pytest.raises(prog.ProgrammingError):
            self._record(msisdn="1" * 21)

        assert _request_rows() == []
        assert _audit_rows() == []


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestProgrammingRequestHistorySemantics:
    def setup_method(self):
        _wipe()
        _seed_hierarchy()
        self.admin = repo.create_or_update_user(
            username="prog-admin", full_name="Prog Admin",
            role="administrator", status="active",
        ).user_id

    def _record(self, device_id=DEVICE_ID, msisdn="0700000000"):
        return prog.record_request(
            device_id=device_id, master_msisdn=msisdn,
            actor_user_id=self.admin,
        )

    def test_repeated_identical_submission_creates_distinct_history(self):
        """PROG-D3: append-only history — no dedupe, every confirm a row."""
        first = self._record()
        second = self._record()

        rows = _request_rows()
        assert len(rows) == 2
        assert first.request_id != second.request_id
        assert all(r["status"] == "pending" for r in rows)
        assert len(_audit_rows()) == 2

    def test_multiple_pending_requests_for_same_device_are_allowed(self):
        """PROG-D4: no single-pending enforcement exists at any layer."""
        other_admin = repo.create_or_update_user(
            username="prog-admin-2", full_name="Prog Admin Two",
            role="administrator", status="active",
        ).user_id

        prog.record_request(
            device_id=DEVICE_ID, master_msisdn="0700000000",
            actor_user_id=self.admin,
        )
        prog.record_request(
            device_id=DEVICE_ID, master_msisdn="0711111111",
            actor_user_id=other_admin,
        )

        statuses = [r["status"] for r in _request_rows()]
        assert statuses == ["pending", "pending"]

    def test_read_back_survives_process_memory_from_postgresql(self):
        """Confirmation state comes from PostgreSQL via a fresh session,
        not from whatever the callback happened to hold."""
        first = self._record()
        second = self._record(msisdn="0711111111")

        recent = prog.recent_requests(DEVICE_ID)
        assert [r.request_id for r in recent] == [
            second.request_id, first.request_id,
        ]
        assert recent[0].master_msisdn == "0711111111"
        assert recent[1].master_msisdn == "0700000000"


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestProgrammingRequestAudit:
    def setup_method(self):
        _wipe()
        _seed_hierarchy()
        self.admin = repo.create_or_update_user(
            username="prog-admin", full_name="Prog Admin",
            role="administrator", status="active",
        ).user_id

    def test_audit_targets_the_device_entity_with_payload_allowlist(self):
        """PROG-D5: entity ("device", device_id); request-specific fields —
        including request_id — travel inside new_values."""
        record = prog.record_request(
            device_id=DEVICE_ID, master_msisdn="0700000000",
            actor_user_id=self.admin,
        )

        rows = _audit_rows()
        assert len(rows) == 1
        row = rows[0]
        assert row["operation"] == audit_cfg.RTL_PROGRAM_REQUESTED
        assert row["entity_type"] == audit_cfg.ENTITY_DEVICE
        assert row["entity_id"] == DEVICE_ID
        assert row["user_id"] == self.admin          # strict D2 actor
        assert row["old_values"] is None             # append-only insert
        assert set(row["new_values"].keys()) == {
            "request_id", "transformer_id", "master_msisdn", "request_method",
        }
        assert row["new_values"]["request_id"] == record.request_id
        assert row["new_values"]["transformer_id"] == TRANSFORMER_ID
        assert row["new_values"]["master_msisdn"] == "0700000000"
        assert row["new_values"]["request_method"] == "dashboard"

    def test_each_accepted_request_audits_exactly_once(self):
        prog.record_request(
            device_id=DEVICE_ID, master_msisdn="0700000000",
            actor_user_id=self.admin,
        )
        prog.record_request(
            device_id=DEVICE_ID, master_msisdn="0711111111",
            actor_user_id=self.admin,
        )

        operations = [r["operation"] for r in _audit_rows()]
        assert operations == [
            audit_cfg.RTL_PROGRAM_REQUESTED,
            audit_cfg.RTL_PROGRAM_REQUESTED,
        ]

    def test_failed_audit_rolls_back_the_request_completely(self, monkeypatch):
        """FWD-D5 atomicity: mutation + audit share one transaction. The
        same failure injection AUD-1 uses must leave NO request row."""

        def explode(**kwargs):
            raise RuntimeError("simulated audit-store outage")

        monkeypatch.setattr(repo, "insert_audit_log", explode)
        with pytest.raises(prog.ProgrammingError):
            prog.record_request(
                device_id=DEVICE_ID, master_msisdn="0700000000",
                actor_user_id=self.admin,
            )

        assert _request_rows() == []
        assert _audit_rows() == []
