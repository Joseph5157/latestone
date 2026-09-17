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


class TestUidPatternValidation:
    """PROG-D8 / FS-PROG-1 §4.4.1: exactly 5 digits. No "29" prefix rule —
    the source labels ``29xxx`` an example, not a requirement."""

    @pytest.mark.parametrize("uid", ["00000", "29017", "99999", "01234"])
    def test_five_digit_uid_matches(self, uid):
        assert prog.UID_PATTERN.fullmatch(uid)

    @pytest.mark.parametrize(
        "uid", ["2901", "290177", "2901a", "29-17", "", "  29017", "29017 "]
    )
    def test_non_conforming_uid_does_not_match(self, uid):
        assert not prog.UID_PATTERN.fullmatch(uid)

    def test_uid_need_not_start_with_29(self):
        """No invented prefix rule: any 5 digits are a valid UID shape."""
        assert prog.UID_PATTERN.fullmatch("10000")


class TestTransformerNameLengthDefenseInDepth:
    """PROG-D8: ``transformer_code`` is already ``VARCHAR(10)``
    (alembic/versions/001_baseline.py), so no real row can ever exceed 10
    characters — this branch can never fire against genuine data. It stays
    as defense-in-depth against a future schema change and is exercised
    here with a mocked breadcrumb, since the database itself refuses to
    store the over-length value this test needs to seed."""

    def test_over_ten_character_transformer_name_rejected(self, monkeypatch):
        fake_breadcrumb = repo.DevicePath(
            plant_id="p1", plant_name="P1", transformer_id="p1-t1",
            transformer_code="12345678901", device_id="p1-t1-d1",
            device_code="29001", device_status="active",
        )
        monkeypatch.setattr(
            repo, "get_device_breadcrumb", lambda device_id: fake_breadcrumb
        )
        with pytest.raises(prog.ProgrammingError):
            prog._validate_programming_identity("p1-t1-d1")

    def test_exactly_ten_character_transformer_name_accepted(self, monkeypatch):
        fake_breadcrumb = repo.DevicePath(
            plant_id="p1", plant_name="P1", transformer_id="p1-t1",
            transformer_code="1234567890", device_id="p1-t1-d1",
            device_code="29001", device_status="active",
        )
        monkeypatch.setattr(
            repo, "get_device_breadcrumb", lambda device_id: fake_breadcrumb
        )
        prog._validate_programming_identity("p1-t1-d1")  # must not raise


# ---------------------------------------------------------------------------
# Database-backed — persisted behaviour on isolated schema
# ---------------------------------------------------------------------------

DEVICE_ID = "prog-p1-t1-d1"
TRANSFORMER_ID = "prog-p1-t1"


def _wipe() -> None:
    """Reset everything this module touches, FK-safe order.

    ``rtl_commands`` before ``rtl_programming_requests`` (RTL-IF-1):
    ``record_request`` now inserts one command per request in the same
    transaction, and ``rtl_commands.request_id`` FK-references
    ``rtl_programming_requests``.
    """
    with session_scope() as session:
        for table in (
            "audit_log", "rtl_commands", "rtl_programming_requests",
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
                f"VALUES ('{DEVICE_ID}', '{TRANSFORMER_ID}', '29001')"
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

    def test_row_projects_to_queued_with_null_completion_columns(self):
        """PROG-D6 (superseded by RTL-PROG-EXEC-1): the request is
        projected to 'queued' the moment its command is created, in the
        same transaction — 'pending' is the insert-time default only, not
        an observable rest state once record_request() has returned."""
        self._record()

        row = _request_rows()[0]
        assert row["status"] == "queued"
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
class TestUidAndTransformerNameServiceValidation:
    """PROG-D8 / FS-PROG-1: the service re-reads the device's OWN persisted
    UID/transformer name from PostgreSQL — never a browser-supplied value —
    and enforces the Functional Specification's two proven §4.4.1 rules
    before a programming request is recorded."""

    def setup_method(self):
        _wipe()
        _seed_hierarchy()
        self.admin = repo.create_or_update_user(
            username="prog-admin", full_name="Prog Admin",
            role="administrator", status="active",
        ).user_id

    def _seed_device(
        self, device_id, device_code, *,
        transformer_code="t1", transformer_id=TRANSFORMER_ID,
    ):
        with session_scope() as session:
            if transformer_id != TRANSFORMER_ID:
                session.execute(
                    text(
                        f"INSERT INTO {repo._SCHEMA}.transformers "
                        f"(transformer_id, plant_id, transformer_code) "
                        f"VALUES ('{transformer_id}', 'prog-p1', "
                        f"'{transformer_code}')"
                    )
                )
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.devices "
                    f"(device_id, transformer_id, device_code) "
                    f"VALUES ('{device_id}', '{transformer_id}', "
                    f"'{device_code}')"
                )
            )

    def _record(self, device_id, msisdn="0700000000"):
        return prog.record_request(
            device_id=device_id, master_msisdn=msisdn,
            actor_user_id=self.admin,
        )

    def test_valid_five_digit_uid_is_accepted(self):
        """DEVICE_ID is seeded with device_code='29001' by _seed_hierarchy."""
        record = self._record(DEVICE_ID)
        assert record.device_id == DEVICE_ID
        assert _request_rows()[0]["status"] == "queued"

    def test_four_digit_uid_rejected(self):
        self._seed_device("prog-p1-t1-d2", "2901")
        with pytest.raises(prog.ProgrammingError):
            self._record("prog-p1-t1-d2")
        assert _request_rows() == []
        assert _audit_rows() == []

    def test_six_digit_uid_rejected(self):
        self._seed_device("prog-p1-t1-d3", "290177")
        with pytest.raises(prog.ProgrammingError):
            self._record("prog-p1-t1-d3")
        assert _request_rows() == []
        assert _audit_rows() == []

    def test_non_numeric_uid_rejected(self):
        self._seed_device("prog-p1-t1-d4", "2901A")
        with pytest.raises(prog.ProgrammingError):
            self._record("prog-p1-t1-d4")
        assert _request_rows() == []
        assert _audit_rows() == []

    def test_transformer_name_exactly_ten_characters_accepted(self):
        self._seed_device(
            "prog-p1-t2-d1", "29010",
            transformer_code="1234567890", transformer_id="prog-p1-t2",
        )
        record = self._record("prog-p1-t2-d1")
        assert record.device_id == "prog-p1-t2-d1"

    def test_uid_checked_before_any_row_is_written_regardless_of_msisdn(self):
        """A malformed UID is refused even with an otherwise-valid MSISDN —
        server/service boundary enforcement, not merely UI presentation."""
        self._seed_device("prog-p1-t1-d6", "1")
        with pytest.raises(prog.ProgrammingError):
            self._record("prog-p1-t1-d6", msisdn="27821234567")
        assert _request_rows() == []


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
        # RTL-PROG-EXEC-1: each accepted request is projected to 'queued'
        # in the same transaction as its command's creation.
        assert all(r["status"] == "queued" for r in rows)
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

        # RTL-PROG-EXEC-1: both project to 'queued' independently.
        statuses = [r["status"] for r in _request_rows()]
        assert statuses == ["queued", "queued"]

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
