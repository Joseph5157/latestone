"""RTL-IF-2 lifecycle transition tests (services/rtl_command_service.py).

Database-backed suites run against the module-scoped isolated_schema
(tests/conftest.py), never the real plant_monitoring tables — same pattern
as tests/test_rtl_commands.py, which this file complements: RTL-IF-1's
request/command creation stays there, RTL-IF-2's state transitions live
here.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from config import commands as command_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import rtl_command_service as cmd
from services import rtl_programming_service as prog

DEVICE_ID = "lc-p1-t1-d1"
TRANSFORMER_ID = "lc-p1-t1"


def _wipe() -> None:
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
                "VALUES ('lc-p1', 'Lifecycle Plant', 'Testland', 0, 0)"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES ('{TRANSFORMER_ID}', 'lc-p1', 't1')"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.devices "
                f"(device_id, transformer_id, device_code) "
                f"VALUES ('{DEVICE_ID}', '{TRANSFORMER_ID}', 'd1')"
            )
        )


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestLifecycleTransitions:
    def setup_method(self):
        _wipe()
        _seed_hierarchy()
        self.admin = repo.create_or_update_user(
            username="lc-admin", full_name="Lc Admin",
            role="administrator", status="active",
        ).user_id
        record = prog.record_request(
            device_id=DEVICE_ID, master_msisdn="0700000000",
            actor_user_id=self.admin,
        )
        self.command_id = cmd.get_command_for_request(record.request_id).command_id

    def test_new_command_is_queued_with_no_lifecycle_timestamps(self):
        """A. Stays QUEUED until explicitly dispatched."""
        command = cmd.get_command(self.command_id)
        assert command.state == command_cfg.STATE_QUEUED
        assert command.sent_at is None
        assert command.acknowledged_at is None
        assert command.completed_at is None
        assert command.failure_code is None
        assert command.failure_detail is None

    def test_success_path_sets_timestamps_at_correct_states(self):
        """B + E. QUEUED -> SENT -> ACKNOWLEDGED -> SUCCEEDED, each
        timestamp set only once its state is reached."""
        sent = cmd.mark_sent(self.command_id)
        assert sent.state == command_cfg.STATE_SENT
        assert sent.sent_at is not None
        assert sent.acknowledged_at is None
        assert sent.completed_at is None

        acked = cmd.mark_acknowledged(self.command_id)
        assert acked.state == command_cfg.STATE_ACKNOWLEDGED
        assert acked.acknowledged_at is not None
        assert acked.completed_at is None
        assert acked.sent_at == sent.sent_at  # untouched by a later transition

        done = cmd.mark_succeeded(self.command_id)
        assert done.state == command_cfg.STATE_SUCCEEDED
        assert done.completed_at is not None
        assert done.failure_code is None
        assert done.failure_detail is None

    def test_failure_path_sets_failure_fields_and_completed_at(self):
        """C. QUEUED -> SENT -> FAILED."""
        cmd.mark_sent(self.command_id)
        failed = cmd.mark_failed(
            self.command_id, failure_code="SIMULATED_FAILURE",
            failure_detail="boom",
        )
        assert failed.state == command_cfg.STATE_FAILED
        assert failed.completed_at is not None
        assert failed.acknowledged_at is None
        assert failed.failure_code == "SIMULATED_FAILURE"
        assert failed.failure_detail == "boom"

    def test_timeout_path_sets_failure_fields_and_completed_at(self):
        """D. QUEUED -> SENT -> TIMED_OUT."""
        cmd.mark_sent(self.command_id)
        timed_out = cmd.mark_timed_out(
            self.command_id, failure_code="SIMULATED_TIMEOUT",
            failure_detail="no response",
        )
        assert timed_out.state == command_cfg.STATE_TIMED_OUT
        assert timed_out.completed_at is not None
        assert timed_out.acknowledged_at is None
        assert timed_out.failure_code == "SIMULATED_TIMEOUT"

    @pytest.mark.parametrize(
        "setup_to_terminal, illegal_target, illegal_call",
        [
            ("succeeded", "SENT", "mark_sent"),
            ("failed", "ACKNOWLEDGED", "mark_acknowledged"),
            ("timed_out", "SENT", "mark_sent"),
        ],
    )
    def test_illegal_transitions_out_of_terminal_states_are_rejected(
        self, setup_to_terminal, illegal_target, illegal_call
    ):
        """F. SUCCEEDED -> SENT, FAILED -> ACKNOWLEDGED, TIMED_OUT -> SENT
        are all refused; terminal states never move backwards (or
        forwards) again."""
        cmd.mark_sent(self.command_id)
        if setup_to_terminal == "succeeded":
            cmd.mark_acknowledged(self.command_id)
            cmd.mark_succeeded(self.command_id)
        elif setup_to_terminal == "failed":
            cmd.mark_failed(self.command_id, failure_code="SIMULATED_FAILURE")
        else:
            cmd.mark_timed_out(self.command_id, failure_code="SIMULATED_TIMEOUT")

        before = cmd.get_command(self.command_id)

        with pytest.raises(cmd.CommandTransitionError):
            getattr(cmd, illegal_call)(self.command_id)

        after = cmd.get_command(self.command_id)
        assert after == before  # the rejected call changed nothing

    def test_queued_cannot_skip_directly_to_acknowledged(self):
        """F. Only QUEUED -> SENT is legal from QUEUED."""
        with pytest.raises(cmd.CommandTransitionError):
            cmd.mark_acknowledged(self.command_id)

    def test_sent_cannot_skip_directly_to_succeeded(self):
        """F. SENT must go through ACKNOWLEDGED, never straight to SUCCEEDED."""
        cmd.mark_sent(self.command_id)
        with pytest.raises(cmd.CommandTransitionError):
            cmd.mark_succeeded(self.command_id)

    def test_unknown_command_id_raises(self):
        with pytest.raises(cmd.CommandTransitionError):
            cmd.mark_sent(999999)

    def test_programming_request_provenance_unchanged_but_status_projects(self):
        """I (revised by RTL-PROG-EXEC-1): provenance columns — everything
        that identifies WHO asked for WHAT — are still untouched by the
        command's entire lifecycle. ``status``/``completed_at``/
        ``error_message`` are the deliberate exception: RTL-PROG-EXEC-1
        makes the request's status a truthful projection of its command,
        so those three are EXPECTED to change, in lockstep with each
        transition."""
        provenance_columns = (
            "request_id, device_id, transformer_id, requested_by, "
            "master_msisdn, requested_at, request_method"
        )
        with session_scope() as session:
            before = dict(
                session.execute(
                    text(
                        f"SELECT {provenance_columns} FROM "
                        f"{repo._SCHEMA}.rtl_programming_requests"
                    )
                ).mappings().one()
            )

        def _status_row():
            with session_scope() as session:
                return dict(
                    session.execute(
                        text(
                            f"SELECT status, completed_at, error_message "
                            f"FROM {repo._SCHEMA}.rtl_programming_requests"
                        )
                    ).mappings().one()
                )

        assert _status_row()["status"] == command_cfg.REQUEST_STATUS_QUEUED

        cmd.mark_sent(self.command_id)
        assert _status_row()["status"] == command_cfg.REQUEST_STATUS_SENT

        cmd.mark_acknowledged(self.command_id)
        sent_state = _status_row()
        assert sent_state["status"] == command_cfg.REQUEST_STATUS_SENT
        assert sent_state["completed_at"] is None

        cmd.mark_succeeded(self.command_id)
        done_state = _status_row()
        assert done_state["status"] == command_cfg.REQUEST_STATUS_SUCCESSFUL
        assert done_state["completed_at"] is not None
        assert done_state["error_message"] is None

        with session_scope() as session:
            after = dict(
                session.execute(
                    text(
                        f"SELECT {provenance_columns} FROM "
                        f"{repo._SCHEMA}.rtl_programming_requests"
                    )
                ).mappings().one()
            )
        assert after == before

    def test_only_one_audit_row_exists_after_full_lifecycle(self):
        """Preserves exactly one RTL_PROGRAM_REQUESTED audit event; no new
        audit event is invented per lifecycle transition."""
        cmd.mark_sent(self.command_id)
        cmd.mark_acknowledged(self.command_id)
        cmd.mark_succeeded(self.command_id)

        with session_scope() as session:
            operations = session.execute(
                text(f"SELECT operation FROM {repo._SCHEMA}.audit_log")
            ).scalars().all()
        assert operations == ["RTL_PROGRAM_REQUESTED"]
