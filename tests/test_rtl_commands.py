"""RTL-IF-1 command persistence tests.

Database-backed suites run against the module-scoped isolated_schema
(tests/conftest.py), never the real plant_monitoring tables — same pattern
as tests/test_rtl_programming.py, which this file complements rather than
duplicates: programming-request-only behaviour (MSISDN validation, PROG-D1
.. D7) stays there. This file covers what RTL-IF-1 adds: the rtl_commands
row created atomically alongside each accepted request.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from config import commands as command_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import rtl_command_service
from services import rtl_programming_service as prog

DEVICE_ID = "cmd-p1-t1-d1"
TRANSFORMER_ID = "cmd-p1-t1"


def _wipe() -> None:
    """Reset everything this module touches, FK-safe order.

    rtl_commands before rtl_programming_requests: rtl_commands.request_id
    FK-references rtl_programming_requests.
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
                "VALUES ('cmd-p1', 'Cmd Plant', 'Testland', 0, 0)"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES ('{TRANSFORMER_ID}', 'cmd-p1', 't1')"
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
                f"SELECT request_id FROM {repo._SCHEMA}.rtl_programming_requests "
                f"ORDER BY request_id"
            )
        ).mappings().fetchall()
    return [dict(r) for r in rows]


def _command_rows() -> list[dict]:
    with session_scope() as session:
        rows = session.execute(
            text(
                f"SELECT command_id, request_id, device_id, command_type, "
                f"state FROM {repo._SCHEMA}.rtl_commands ORDER BY command_id"
            )
        ).mappings().fetchall()
    return [dict(r) for r in rows]


def _audit_rows() -> list[dict]:
    with session_scope() as session:
        rows = session.execute(
            text(f"SELECT operation FROM {repo._SCHEMA}.audit_log ORDER BY audit_id")
        ).mappings().fetchall()
    return [dict(r) for r in rows]


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestAcceptedRequestCreatesOneCommand:
    """A. Authorized programming request creates one request and one command."""

    def setup_method(self):
        _wipe()
        _seed_hierarchy()
        self.admin = repo.create_or_update_user(
            username="cmd-admin", full_name="Cmd Admin",
            role="administrator", status="active",
        ).user_id

    def _record(self, device_id=DEVICE_ID, msisdn="0700000000"):
        return prog.record_request(
            device_id=device_id, master_msisdn=msisdn,
            actor_user_id=self.admin,
        )

    def test_one_request_and_one_command_are_created(self):
        self._record()

        assert len(_request_rows()) == 1
        assert len(_command_rows()) == 1

    def test_command_references_the_correct_request_and_device(self):
        """B. Command references correct request, correct device, PROGRAM_RTL
        type, starts QUEUED."""
        record = self._record()

        rows = _command_rows()
        assert len(rows) == 1
        row = rows[0]
        assert row["request_id"] == record.request_id
        assert row["device_id"] == record.device_id
        assert row["command_type"] == command_cfg.COMMAND_TYPE_PROGRAM_RTL
        assert row["state"] == command_cfg.STATE_QUEUED

    def test_read_api_resolves_request_to_its_command(self):
        record = self._record()

        command = rtl_command_service.get_command_for_request(record.request_id)
        assert command is not None
        assert command.request_id == record.request_id
        assert command.device_id == record.device_id
        assert command.command_type == command_cfg.COMMAND_TYPE_PROGRAM_RTL
        assert command.state == command_cfg.STATE_QUEUED

    def test_unknown_request_resolves_to_no_command(self):
        assert rtl_command_service.get_command_for_request(999999) is None

    def test_existing_request_row_is_unchanged_by_command_creation(self):
        """C. The programming request stays the append-only intent record —
        RTL-IF-1 adds a command, it does not alter the request."""
        record = self._record()

        rows = _request_rows()
        assert len(rows) == 1
        assert rows[0]["request_id"] == record.request_id
        # Only one audit row (RTL_PROGRAM_REQUESTED): no second audit event
        # is invented merely because a command row was also created.
        audits = _audit_rows()
        assert len(audits) == 1


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestTwoAcceptedRequestsCreateTwoCommands:
    """D. Two accepted requests for the same RTL create two request rows
    and two distinct command rows."""

    def setup_method(self):
        _wipe()
        _seed_hierarchy()
        self.admin = repo.create_or_update_user(
            username="cmd-admin", full_name="Cmd Admin",
            role="administrator", status="active",
        ).user_id

    def test_two_requests_produce_two_distinct_commands(self):
        first = prog.record_request(
            device_id=DEVICE_ID, master_msisdn="0700000000",
            actor_user_id=self.admin,
        )
        second = prog.record_request(
            device_id=DEVICE_ID, master_msisdn="0711111111",
            actor_user_id=self.admin,
        )

        requests = _request_rows()
        commands = _command_rows()
        assert len(requests) == 2
        assert len(commands) == 2
        assert first.request_id != second.request_id

        by_request = {c["request_id"]: c for c in commands}
        assert set(by_request) == {first.request_id, second.request_id}
        assert by_request[first.request_id]["command_id"] != (
            by_request[second.request_id]["command_id"]
        )


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestOneRequestCannotObtainTwoCommands:
    """E. One request cannot obtain two commands."""

    def setup_method(self):
        _wipe()
        _seed_hierarchy()
        self.admin = repo.create_or_update_user(
            username="cmd-admin", full_name="Cmd Admin",
            role="administrator", status="active",
        ).user_id

    def test_second_command_for_the_same_request_is_rejected(self):
        record = prog.record_request(
            device_id=DEVICE_ID, master_msisdn="0700000000",
            actor_user_id=self.admin,
        )
        assert len(_command_rows()) == 1

        with pytest.raises(Exception):
            repo.create_command(
                request_id=record.request_id,
                command_type=command_cfg.COMMAND_TYPE_PROGRAM_RTL,
                state=command_cfg.STATE_QUEUED,
            )

        assert len(_command_rows()) == 1

    def test_unknown_request_id_raises_value_error(self):
        with pytest.raises(ValueError):
            repo.create_command(
                request_id=999999,
                command_type=command_cfg.COMMAND_TYPE_PROGRAM_RTL,
                state=command_cfg.STATE_QUEUED,
            )


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestTransactionAtomicity:
    """F. If command insertion fails, request + audit are rolled back."""

    def setup_method(self):
        _wipe()
        _seed_hierarchy()
        self.admin = repo.create_or_update_user(
            username="cmd-admin", full_name="Cmd Admin",
            role="administrator", status="active",
        ).user_id

    def test_failed_command_insert_rolls_back_the_request_and_audit(
        self, monkeypatch
    ):
        def explode(**kwargs):
            raise RuntimeError("simulated command-store outage")

        monkeypatch.setattr(repo, "create_command", explode)

        with pytest.raises(prog.ProgrammingError):
            prog.record_request(
                device_id=DEVICE_ID, master_msisdn="0700000000",
                actor_user_id=self.admin,
            )

        assert _request_rows() == []
        assert _command_rows() == []
        assert _audit_rows() == []
