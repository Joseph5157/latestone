"""RTL-IF-2 dispatcher + SimulatorTransport integration tests.

Database-backed suites run against the module-scoped isolated_schema
(tests/conftest.py), never the real plant_monitoring tables.
"""
from __future__ import annotations

import socket

import pytest
from sqlalchemy import text

from config import commands as command_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import rtl_command_dispatch_service as dispatch
from services import rtl_command_service as cmd
from services import rtl_programming_service as prog
from services.device_transport import TransportOutcome, TRANSPORT_RESULT_SUCCESS
from services.simulator_transport import (
    OUTCOME_FAILURE,
    OUTCOME_SUCCESS,
    OUTCOME_TIMEOUT,
    SimulatorTransport,
)

DEVICE_ID = "disp-p1-t1-d1"
TRANSFORMER_ID = "disp-p1-t1"


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
                "VALUES ('disp-p1', 'Dispatch Plant', 'Testland', 0, 0)"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES ('{TRANSFORMER_ID}', 'disp-p1', 't1')"
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
class TestDispatchOutcomes:
    def setup_method(self):
        _wipe()
        _seed_hierarchy()
        self.admin = repo.create_or_update_user(
            username="disp-admin", full_name="Disp Admin",
            role="administrator", status="active",
        ).user_id

    def _new_command_id(self) -> int:
        record = prog.record_request(
            device_id=DEVICE_ID, master_msisdn="0700000000",
            actor_user_id=self.admin,
        )
        return cmd.get_command_for_request(record.request_id).command_id

    def test_a_new_command_stays_queued_until_dispatched(self):
        """A. record_request() alone never advances the command past QUEUED."""
        command_id = self._new_command_id()
        assert cmd.get_command(command_id).state == command_cfg.STATE_QUEUED

    def test_b_success_reaches_succeeded_through_acknowledged(self):
        """B. QUEUED -> SENT -> ACKNOWLEDGED -> SUCCEEDED."""
        command_id = self._new_command_id()
        result = dispatch.dispatch_command(
            command_id, SimulatorTransport(OUTCOME_SUCCESS)
        )
        assert result.state == command_cfg.STATE_SUCCEEDED
        assert result.sent_at is not None
        assert result.acknowledged_at is not None
        assert result.completed_at is not None
        assert result.failure_code is None

    def test_c_failure_reaches_failed_directly_from_sent(self):
        """C. QUEUED -> SENT -> FAILED (never ACKNOWLEDGED)."""
        command_id = self._new_command_id()
        result = dispatch.dispatch_command(
            command_id, SimulatorTransport(OUTCOME_FAILURE)
        )
        assert result.state == command_cfg.STATE_FAILED
        assert result.sent_at is not None
        assert result.acknowledged_at is None
        assert result.completed_at is not None
        assert result.failure_code == command_cfg.FAILURE_CODE_SIMULATED_FAILURE
        assert result.failure_detail

    def test_d_timeout_reaches_timed_out_directly_from_sent(self):
        """D. QUEUED -> SENT -> TIMED_OUT (never ACKNOWLEDGED)."""
        command_id = self._new_command_id()
        result = dispatch.dispatch_command(
            command_id, SimulatorTransport(OUTCOME_TIMEOUT)
        )
        assert result.state == command_cfg.STATE_TIMED_OUT
        assert result.acknowledged_at is None
        assert result.completed_at is not None
        assert result.failure_code == command_cfg.FAILURE_CODE_SIMULATED_TIMEOUT

    @pytest.mark.parametrize(
        "outcome", [OUTCOME_SUCCESS, OUTCOME_FAILURE, OUTCOME_TIMEOUT]
    )
    def test_g_terminal_command_is_not_re_dispatched(self, outcome):
        """G. A second dispatch of an already-terminal command is refused
        loudly, not silently re-run."""
        command_id = self._new_command_id()
        dispatch.dispatch_command(command_id, SimulatorTransport(outcome))
        terminal_state = cmd.get_command(command_id).state

        with pytest.raises(dispatch.CommandNotDispatchableError):
            dispatch.dispatch_command(command_id, SimulatorTransport(OUTCOME_SUCCESS))

        # Refused, not silently redone: state is exactly what it was.
        assert cmd.get_command(command_id).state == terminal_state

    def test_g_in_flight_sent_command_is_not_re_dispatched(self):
        """G, extended: SENT (not yet terminal) is also refused, not just
        the three terminal states — re-running an in-flight command is
        exactly as wrong as re-running a finished one."""
        command_id = self._new_command_id()
        cmd.mark_sent(command_id)

        with pytest.raises(dispatch.CommandNotDispatchableError):
            dispatch.dispatch_command(command_id, SimulatorTransport(OUTCOME_SUCCESS))

    def test_h_simulator_performs_no_network_call(self, monkeypatch):
        """H. Patch socket.socket to explode on construction; dispatching
        through SimulatorTransport must never touch it."""

        def _explode(*args, **kwargs):
            raise AssertionError("SimulatorTransport attempted a network call")

        monkeypatch.setattr(socket, "socket", _explode)

        command_id = self._new_command_id()
        result = dispatch.dispatch_command(
            command_id, SimulatorTransport(OUTCOME_SUCCESS)
        )
        assert result.state == command_cfg.STATE_SUCCEEDED

    def test_i_programming_request_provenance_unchanged_after_dispatch(self):
        """I. The request row is byte-for-byte unchanged by a full
        successful dispatch."""
        record = prog.record_request(
            device_id=DEVICE_ID, master_msisdn="0700000000",
            actor_user_id=self.admin,
        )
        command_id = cmd.get_command_for_request(record.request_id).command_id

        with session_scope() as session:
            before = dict(
                session.execute(
                    text(
                        f"SELECT request_id, device_id, transformer_id, "
                        f"requested_by, master_msisdn, requested_at, "
                        f"request_method, status, completed_at, error_message "
                        f"FROM {repo._SCHEMA}.rtl_programming_requests "
                        f"WHERE request_id = :rid"
                    ),
                    {"rid": record.request_id},
                ).mappings().one()
            )

        dispatch.dispatch_command(command_id, SimulatorTransport(OUTCOME_SUCCESS))

        with session_scope() as session:
            after = dict(
                session.execute(
                    text(
                        f"SELECT request_id, device_id, transformer_id, "
                        f"requested_by, master_msisdn, requested_at, "
                        f"request_method, status, completed_at, error_message "
                        f"FROM {repo._SCHEMA}.rtl_programming_requests "
                        f"WHERE request_id = :rid"
                    ),
                    {"rid": record.request_id},
                ).mappings().one()
            )
        assert after == before

    def test_l_transport_exception_leaves_command_at_sent_not_corrupted(self):
        """L. A transport bug (raises instead of returning an outcome)
        leaves the command exactly at SENT — a genuine, non-terminal,
        coherent resting state — never a partial/impossible combination."""

        class ExplodingTransport:
            def send(self, command, request):
                raise RuntimeError("simulated transport-implementation bug")

        command_id = self._new_command_id()

        with pytest.raises(RuntimeError):
            dispatch.dispatch_command(command_id, ExplodingTransport())

        command = cmd.get_command(command_id)
        assert command.state == command_cfg.STATE_SENT
        assert command.sent_at is not None
        assert command.acknowledged_at is None
        assert command.completed_at is None
        assert command.failure_code is None

        # And the command is still coherently resumable: a legal transition
        # from SENT still succeeds afterward.
        result = cmd.mark_failed(command_id, failure_code="SIMULATED_FAILURE")
        assert result.state == command_cfg.STATE_FAILED

    def test_unknown_command_id_is_not_dispatchable(self):
        with pytest.raises(dispatch.CommandNotDispatchableError):
            dispatch.dispatch_command(999999, SimulatorTransport(OUTCOME_SUCCESS))

    def test_unknown_transport_result_is_refused(self):
        class BadTransport:
            def send(self, command, request):
                return TransportOutcome(result="NOT_A_REAL_RESULT")

        command_id = self._new_command_id()
        with pytest.raises(dispatch.CommandNotDispatchableError):
            dispatch.dispatch_command(command_id, BadTransport())

    def test_simulator_transport_rejects_unknown_outcome(self):
        with pytest.raises(ValueError):
            SimulatorTransport("NOT_A_REAL_OUTCOME")

    def test_simulator_transport_send_result_matches_configured_outcome(self):
        """Direct transport-level check, independent of the dispatcher."""
        command_id = self._new_command_id()
        command = cmd.get_command(command_id)
        request = repo.get_programming_request(command.request_id)

        outcome = SimulatorTransport(OUTCOME_SUCCESS).send(command, request)
        assert outcome.result == TRANSPORT_RESULT_SUCCESS
        assert outcome.failure_code is None
