"""RTL-PROG-EXEC-1 tests: command<->request reconciliation and the new
execution/orchestration service.

Database-backed suites run against the module-scoped isolated_schema
(tests/conftest.py), never the real plant_monitoring tables — same pattern
as tests/test_rtl_programming.py, tests/test_rtl_commands.py,
tests/test_rtl_command_service_lifecycle.py and
tests/test_rtl_command_dispatch.py, which this file complements: those
cover request creation, command creation, command-lifecycle transitions
and dispatcher/transport behaviour respectively; this file covers only
what RTL-PROG-EXEC-1 adds — the request-status projection those
transitions now carry, and services/rtl_programming_execution_service.py.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from config import commands as command_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import rtl_command_dispatch_service as dispatch
from services import rtl_command_service as cmd
from services import rtl_programming_execution_service as execution
from services import rtl_programming_service as prog
from services.simulator_transport import (
    OUTCOME_FAILURE,
    OUTCOME_SUCCESS,
    OUTCOME_TIMEOUT,
    SimulatorTransport,
)

DEVICE_ID = "exec-p1-t1-d1"
TRANSFORMER_ID = "exec-p1-t1"


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
                "VALUES ('exec-p1', 'Exec Plant', 'Testland', 0, 0)"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES ('{TRANSFORMER_ID}', 'exec-p1', 't1')"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.devices "
                f"(device_id, transformer_id, device_code) "
                f"VALUES ('{DEVICE_ID}', '{TRANSFORMER_ID}', '29001')"
            )
        )


def _request_row(request_id: int) -> dict:
    with session_scope() as session:
        row = session.execute(
            text(
                f"SELECT status, completed_at, error_message "
                f"FROM {repo._SCHEMA}.rtl_programming_requests "
                f"WHERE request_id = :rid"
            ),
            {"rid": request_id},
        ).mappings().one()
    return dict(row)


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestRequestStatusProjection:
    def setup_method(self):
        _wipe()
        _seed_hierarchy()
        self.admin = repo.create_or_update_user(
            username="exec-admin", full_name="Exec Admin",
            role="administrator", status="active",
        ).user_id

    def _new_request_and_command(self, msisdn="0700000000"):
        record = prog.record_request(
            device_id=DEVICE_ID, master_msisdn=msisdn, actor_user_id=self.admin,
        )
        command_id = cmd.get_command_for_request(record.request_id).command_id
        return record, command_id

    def test_request_creation_ends_queued(self):
        """record_request() projects the request to 'queued' the moment
        its QUEUED command exists, in the same transaction — not left at
        the insert-time 'pending' default."""
        record, _command_id = self._new_request_and_command()
        assert record.status == command_cfg.REQUEST_STATUS_QUEUED
        assert record.completed_at is None
        assert record.error_message is None

        row = _request_row(record.request_id)
        assert row["status"] == command_cfg.REQUEST_STATUS_QUEUED
        assert row["completed_at"] is None
        assert row["error_message"] is None

    def test_sent_and_acknowledged_both_project_to_sent(self):
        """SENT and ACKNOWLEDGED are both observed by the request as
        'sent' — the request lifecycle does not distinguish them."""
        record, command_id = self._new_request_and_command()

        cmd.mark_sent(command_id)
        row = _request_row(record.request_id)
        assert row["status"] == command_cfg.REQUEST_STATUS_SENT
        assert row["completed_at"] is None

        cmd.mark_acknowledged(command_id)
        row = _request_row(record.request_id)
        assert row["status"] == command_cfg.REQUEST_STATUS_SENT
        assert row["completed_at"] is None

    def test_success_path_projects_successful_with_completed_at_and_no_error(self):
        record, command_id = self._new_request_and_command()
        cmd.mark_sent(command_id)
        cmd.mark_acknowledged(command_id)
        cmd.mark_succeeded(command_id)

        row = _request_row(record.request_id)
        assert row["status"] == command_cfg.REQUEST_STATUS_SUCCESSFUL
        assert row["completed_at"] is not None
        assert row["error_message"] is None

    def test_failure_path_projects_failed_with_safe_normalized_message(self):
        """The projected error_message is the command's own normalized
        failure_code (+ its bounded failure_detail) — never a raw
        exception or stack trace, matching ADR-018's transport contract."""
        record, command_id = self._new_request_and_command()
        cmd.mark_sent(command_id)
        cmd.mark_failed(
            command_id, failure_code="SIMULATED_FAILURE",
            failure_detail="Simulated transport failure.",
        )

        row = _request_row(record.request_id)
        assert row["status"] == command_cfg.REQUEST_STATUS_FAILED
        assert row["completed_at"] is not None
        assert row["error_message"] == (
            "SIMULATED_FAILURE: Simulated transport failure."
        )

    def test_timeout_path_also_projects_failed(self):
        """The request lifecycle has no separate timeout status — TIMED_OUT
        projects the same as FAILED (config.commands.
        REQUEST_STATUS_FOR_COMMAND_STATE)."""
        record, command_id = self._new_request_and_command()
        cmd.mark_sent(command_id)
        cmd.mark_timed_out(
            command_id, failure_code="SIMULATED_TIMEOUT",
            failure_detail="Simulated transport timeout.",
        )

        row = _request_row(record.request_id)
        assert row["status"] == command_cfg.REQUEST_STATUS_FAILED
        assert row["completed_at"] is not None
        assert row["error_message"] == (
            "SIMULATED_TIMEOUT: Simulated transport timeout."
        )

    def test_completed_at_is_set_only_on_terminal_projections(self):
        record, command_id = self._new_request_and_command()
        assert _request_row(record.request_id)["completed_at"] is None

        cmd.mark_sent(command_id)
        assert _request_row(record.request_id)["completed_at"] is None

        cmd.mark_acknowledged(command_id)
        assert _request_row(record.request_id)["completed_at"] is None

        cmd.mark_succeeded(command_id)
        assert _request_row(record.request_id)["completed_at"] is not None

    def test_illegal_transition_is_refused_and_request_projection_untouched(self):
        """A refused transition (SENT -> SUCCEEDED, skipping ACKNOWLEDGED)
        must not touch the request at all — the command's own legality
        check runs before any database write."""
        record, command_id = self._new_request_and_command()
        cmd.mark_sent(command_id)
        before = _request_row(record.request_id)

        with pytest.raises(cmd.CommandTransitionError):
            cmd.mark_succeeded(command_id)

        assert _request_row(record.request_id) == before

    def test_concurrent_transition_loses_at_the_db_layer_before_any_projection(self):
        """Two callers racing on the same command: the second, stale
        conditional UPDATE affects zero rows and raises before the request
        is ever touched — repo.update_command_state's
        `WHERE state = :expected_state` is the whole safety story
        (ADR-018), and it is checked strictly before
        update_programming_request_status is ever called."""
        record, command_id = self._new_request_and_command()
        cmd.mark_sent(command_id)  # QUEUED -> SENT, request projects to 'sent'

        # A second caller that read the command while it was still QUEUED
        # now tries the same conditional UPDATE directly at the repository
        # layer (bypassing the legality pre-check, which is exactly what a
        # stale concurrent read would do).
        with pytest.raises(ValueError):
            repo.update_command_state(
                command_id,
                expected_state=command_cfg.STATE_QUEUED,
                to_state=command_cfg.STATE_SENT,
                timestamp_column="sent_at",
            )

        assert cmd.get_command(command_id).state == command_cfg.STATE_SENT
        assert _request_row(record.request_id)["status"] == (
            command_cfg.REQUEST_STATUS_SENT
        )

    def test_failed_request_projection_rolls_back_the_command_transition(
        self, monkeypatch
    ):
        """If the request-projection write fails, the command's own
        conditional UPDATE rolls back with it — the two can never diverge
        (no command/request split-brain)."""
        record, command_id = self._new_request_and_command()

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated request-projection outage")

        monkeypatch.setattr(repo, "update_programming_request_status", _boom)

        with pytest.raises(RuntimeError):
            cmd.mark_sent(command_id)

        monkeypatch.undo()
        assert cmd.get_command(command_id).state == command_cfg.STATE_QUEUED
        assert _request_row(record.request_id)["status"] == (
            command_cfg.REQUEST_STATUS_QUEUED
        )

    def test_failed_initial_projection_rolls_back_the_whole_request(
        self, monkeypatch
    ):
        """The same guarantee at request-creation time: if projecting the
        brand-new command's QUEUED state onto the request fails,
        record_request()'s whole transaction (request + command + audit)
        rolls back — PROG-D3/FWD-D5 atomicity, unchanged."""

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated request-projection outage")

        monkeypatch.setattr(repo, "update_programming_request_status", _boom)

        with pytest.raises(prog.ProgrammingError):
            prog.record_request(
                device_id=DEVICE_ID, master_msisdn="0700000000",
                actor_user_id=self.admin,
            )

        monkeypatch.undo()
        with session_scope() as session:
            assert session.execute(
                text(f"SELECT count(*) FROM {repo._SCHEMA}.rtl_programming_requests")
            ).scalar() == 0
            assert session.execute(
                text(f"SELECT count(*) FROM {repo._SCHEMA}.rtl_commands")
            ).scalar() == 0
            assert session.execute(
                text(f"SELECT count(*) FROM {repo._SCHEMA}.audit_log")
            ).scalar() == 0


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestDispatchRefusalLeavesProjectionUntouched:
    def setup_method(self):
        _wipe()
        _seed_hierarchy()
        self.admin = repo.create_or_update_user(
            username="exec-admin", full_name="Exec Admin",
            role="administrator", status="active",
        ).user_id

    def _new_request_and_command(self, msisdn="0700000000"):
        record = prog.record_request(
            device_id=DEVICE_ID, master_msisdn=msisdn, actor_user_id=self.admin,
        )
        command_id = cmd.get_command_for_request(record.request_id).command_id
        return record, command_id

    @pytest.mark.parametrize(
        "outcome", [OUTCOME_SUCCESS, OUTCOME_FAILURE, OUTCOME_TIMEOUT]
    )
    def test_illegal_redispatch_refusal_leaves_request_projection_unchanged(
        self, outcome
    ):
        record, command_id = self._new_request_and_command()
        dispatch.dispatch_command(command_id, SimulatorTransport(outcome))
        before = _request_row(record.request_id)

        with pytest.raises(dispatch.CommandNotDispatchableError):
            dispatch.dispatch_command(command_id, SimulatorTransport(OUTCOME_SUCCESS))

        assert _request_row(record.request_id) == before


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestExecutionService:
    """services/rtl_programming_execution_service.py — the protocol-neutral
    orchestration entry point, DeviceTransport injected."""

    def setup_method(self):
        _wipe()
        _seed_hierarchy()
        self.admin = repo.create_or_update_user(
            username="exec-admin", full_name="Exec Admin",
            role="administrator", status="active",
        ).user_id

    def _new_request(self, msisdn="0700000000"):
        return prog.record_request(
            device_id=DEVICE_ID, master_msisdn=msisdn, actor_user_id=self.admin,
        )

    def test_execute_request_dispatches_the_requests_existing_command(self):
        record = self._new_request()

        result = execution.execute_request(
            record.request_id, SimulatorTransport(OUTCOME_SUCCESS)
        )

        assert result.state == command_cfg.STATE_SUCCEEDED
        assert result.request_id == record.request_id
        row = _request_row(record.request_id)
        assert row["status"] == command_cfg.REQUEST_STATUS_SUCCESSFUL

    def test_execute_request_propagates_a_failure_outcome(self):
        record = self._new_request()

        result = execution.execute_request(
            record.request_id, SimulatorTransport(OUTCOME_FAILURE)
        )

        assert result.state == command_cfg.STATE_FAILED
        row = _request_row(record.request_id)
        assert row["status"] == command_cfg.REQUEST_STATUS_FAILED
        assert row["error_message"]

    def test_execute_request_unknown_request_id_raises(self):
        with pytest.raises(execution.ProgrammingExecutionError):
            execution.execute_request(999999, SimulatorTransport(OUTCOME_SUCCESS))

    def test_execute_request_refuses_an_already_dispatched_command(self):
        """Repeated execution of the same request is refused loudly, not
        silently re-run — the same command-level guarantee
        rtl_command_dispatch_service.dispatch_command already provides,
        surfaced through this module's own exception type."""
        record = self._new_request()
        execution.execute_request(record.request_id, SimulatorTransport(OUTCOME_SUCCESS))

        with pytest.raises(execution.ProgrammingExecutionError):
            execution.execute_request(
                record.request_id, SimulatorTransport(OUTCOME_SUCCESS)
            )

    def test_execute_request_never_constructs_a_transport_itself(self):
        """Protocol-neutral by construction: this module does not import
        SimulatorTransport, so it cannot default to one."""
        import ast
        import inspect

        source = inspect.getsource(execution)
        tree = ast.parse(source)
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
        assert "SimulatorTransport" not in names
        assert not any("simulator" in n.lower() for n in names)
