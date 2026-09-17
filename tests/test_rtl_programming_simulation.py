"""RTL-PROG-SIM-1 tests: the development-only simulated programming
execution path, and the boundary that keeps it out of production.

Three layers, deliberately separated:

- **Configuration** (`config/settings.py`): default off, explicit
  development opt-in, fail-closed in production. Pure, no Dash, no DB.
- **Component/callback** (`components/device_manage_drawer.py`,
  `callbacks/rtl_programming_simulation.py`): controls absent when
  disabled, authorization re-checked on every press, browser-supplied
  request ids treated as untrusted. Service calls are spied, so these
  prove the CALLBACK's boundary rather than the lifecycle underneath it.
- **Database** (`@pytest.mark.db`): the three simulated outcomes actually
  reaching the request's persisted status, against the module-scoped
  isolated_schema — never the real plant_monitoring tables.
"""
from __future__ import annotations

import ast
import contextlib
import inspect

import pytest
from dash import no_update
from dash.development.base_component import Component
from sqlalchemy import text

from components import device_manage_drawer as drawer
from components.status_panels import ACTION_REFUSED_CLASS
from config import commands as command_cfg
from config import settings
from config.settings import (
    ProgrammingSimulatorSettings,
    resolve_programming_simulator_enabled,
)
from db.engine import session_scope
from callbacks import device_manage, rtl_programming_simulation
from repositories import plant_monitoring_repository as repo
from services import rtl_command_service as cmd
from services import rtl_programming_execution_service as execution
from services import rtl_programming_service as prog
from services import rtl_programming_simulation_service as simulation
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN
from services.simulator_transport import (
    OUTCOME_FAILURE,
    OUTCOME_SUCCESS,
    OUTCOME_TIMEOUT,
)
from tests.auth_test_support import no_trusted_session, trusted_session


# ---------------------------------------------------------------------------
# Configuration boundary — pure
# ---------------------------------------------------------------------------


class TestSimulatorEnablementResolution:
    """`resolve_programming_simulator_enabled` is the single decision point.
    Everything else in this gate keys off its answer."""

    @pytest.mark.parametrize("raw", ["", "   ", "false", "0", "no", "off", "maybe"])
    def test_disabled_by_default_and_for_any_non_truthy_value(self, raw):
        assert resolve_programming_simulator_enabled("development", raw) is False

    @pytest.mark.parametrize("raw", ["1", "true", "TRUE", " yes ", "on"])
    def test_explicit_development_enablement(self, raw):
        assert resolve_programming_simulator_enabled("development", raw) is True

    @pytest.mark.parametrize("raw", ["1", "true", "yes", "on"])
    def test_production_enable_attempt_fails_closed(self, raw):
        """Not silently False — an operator who asked a production
        deployment to simulate holds a mistaken belief about what it is
        doing, and quietly ignoring the request would leave it intact."""
        with pytest.raises(RuntimeError) as excinfo:
            resolve_programming_simulator_enabled("production", raw)
        assert "RTL_PROGRAMMING_SIMULATOR_ENABLED" in str(excinfo.value)

    def test_production_without_the_setting_is_simply_disabled(self):
        """Production is only refused when simulation was actually asked
        for — an ordinary production deployment starts normally."""
        assert resolve_programming_simulator_enabled("production", "") is False

    def test_the_shipped_default_is_off(self):
        """The setting the application ships with resolves to disabled, and
        this test process is genuinely running with it off.

        The second assertion is a precondition for the rest of this file:
        the "controls hidden", "no callback registered" and "disabled
        executes nothing" tests below all describe the disabled path. If a
        developer has `RTL_PROGRAMMING_SIMULATOR_ENABLED` set in their own
        `.env` for a demo, this names the reason those fail rather than
        leaving it to be puzzled out.
        """
        assert resolve_programming_simulator_enabled("development", "") is False
        assert simulation.is_simulation_enabled() is False, (
            "this suite must run with the simulator off — unset "
            "RTL_PROGRAMMING_SIMULATOR_ENABLED in your .env"
        )


@contextlib.contextmanager
def _simulation_enabled(monkeypatch, *, enabled: bool = True, production: bool = False):
    """Run the block with the simulator explicitly enabled/disabled.

    Patches the resolved settings objects rather than
    `is_simulation_enabled` itself, so the real predicate — including its
    "and not production" re-check — is the thing under test.
    """
    monkeypatch.setattr(
        settings, "programming_simulator", ProgrammingSimulatorSettings(enabled=enabled)
    )
    monkeypatch.setattr(settings, "IS_PRODUCTION", production)
    yield


class TestIsSimulationEnabled:
    def test_disabled_by_default(self):
        assert simulation.is_simulation_enabled() is False

    def test_enabled_when_explicitly_configured_outside_production(self, monkeypatch):
        with _simulation_enabled(monkeypatch):
            assert simulation.is_simulation_enabled() is True

    def test_production_can_never_be_enabled_even_if_the_flag_says_so(
        self, monkeypatch
    ):
        """Defence in depth: configuration resolution already refuses this
        combination, so it should be unreachable — the predicate refuses it
        anyway rather than trusting that."""
        with _simulation_enabled(monkeypatch, enabled=True, production=True):
            assert simulation.is_simulation_enabled() is False


class TestSimulationServiceRefusals:
    def test_simulating_while_disabled_raises_rather_than_doing_nothing(self):
        with pytest.raises(simulation.SimulationDisabledError):
            simulation.simulate_request_execution(
                request_id=1, outcome=OUTCOME_SUCCESS
            )

    def test_unknown_outcome_is_refused(self, monkeypatch):
        with _simulation_enabled(monkeypatch):
            with pytest.raises(simulation.SimulationOutcomeError):
                simulation.simulate_request_execution(
                    request_id=1, outcome="NOT_A_REAL_OUTCOME"
                )

    def test_no_transport_is_constructed_when_disabled(self, monkeypatch):
        """The refusal must land BEFORE a SimulatorTransport exists."""
        constructed = []
        monkeypatch.setattr(
            simulation,
            "SimulatorTransport",
            lambda outcome: constructed.append(outcome),
        )

        with pytest.raises(simulation.SimulationDisabledError):
            simulation.simulate_request_execution(
                request_id=1, outcome=OUTCOME_SUCCESS
            )
        assert constructed == []


# ---------------------------------------------------------------------------
# UI presence — controls exist only when explicitly enabled
# ---------------------------------------------------------------------------


def _collect_ids(node) -> set[str]:
    """Every component id in a Dash tree — same shape as
    tests/test_equipment_selector.py's `collect_ids`, including its
    `Component` guard (without it, a leaf string's absent `children`
    recurses on None forever)."""
    found: set[str] = set()

    def walk(n):
        if isinstance(n, (list, tuple)):
            for item in n:
                walk(item)
            return
        if not isinstance(n, Component):
            return
        node_id = getattr(n, "id", None)
        if isinstance(node_id, str):
            found.add(node_id)
        walk(getattr(n, "children", None))

    walk(node)
    return found


_SIMULATION_CONTROL_IDS = {
    drawer.PROGRAM_RTL_SIM_SECTION_ID,
    drawer.PROGRAM_RTL_SIM_OUTCOME_ID,
    drawer.PROGRAM_RTL_SIM_BTN,
    drawer.PROGRAM_RTL_SIM_RESULT_ID,
}


class TestSimulationControlsVisibility:
    def test_controls_do_not_render_when_disabled(self):
        ids = _collect_ids(drawer.device_manage_drawer())
        assert not (_SIMULATION_CONTROL_IDS & ids), (
            "the simulation controls must not exist at all by default — "
            "there must be nothing hidden for a browser to re-enable"
        )

    def test_controls_render_when_explicitly_enabled(self, monkeypatch):
        with _simulation_enabled(monkeypatch):
            ids = _collect_ids(drawer.device_manage_drawer())
        assert _SIMULATION_CONTROL_IDS <= ids

    def test_the_request_store_is_present_in_both_modes(self, monkeypatch):
        """The store is not simulator-specific — keeping it always present
        is what lets `confirm_program_rtl` have one output shape in every
        environment."""
        assert drawer.PROGRAM_RTL_LAST_REQUEST_ID in _collect_ids(
            drawer.device_manage_drawer()
        )
        with _simulation_enabled(monkeypatch):
            assert drawer.PROGRAM_RTL_LAST_REQUEST_ID in _collect_ids(
                drawer.device_manage_drawer()
            )

    def test_the_controls_carry_the_simulation_notice(self, monkeypatch):
        with _simulation_enabled(monkeypatch):
            rendered = str(drawer.device_manage_drawer())
        assert drawer.SIMULATION_NOTICE in rendered
        assert "not evidence that any physical RTL was programmed" in rendered

    def test_every_offered_outcome_is_labelled_as_simulated(self, monkeypatch):
        """No option may read as a real device response."""
        with _simulation_enabled(monkeypatch):
            panel = drawer.program_rtl_simulation_controls()

        def find(node, target):
            if getattr(node, "id", None) == target:
                return node
            for child in getattr(node, "children", None) or []:
                found = find(child, target) if hasattr(child, "children") or hasattr(child, "id") else None
                if found is not None:
                    return found
            return None

        dropdown = find(panel, drawer.PROGRAM_RTL_SIM_OUTCOME_ID)
        assert dropdown is not None
        assert {opt["value"] for opt in dropdown.options} == set(
            simulation.SIMULATION_OUTCOMES
        )
        for option in dropdown.options:
            assert option["label"].lower().startswith("simulated")


class _CapturingApp:
    def __init__(self):
        self.functions = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions[fn.__name__] = fn
            return fn

        return decorator


class TestCallbackRegistration:
    def test_no_callback_is_registered_when_disabled(self):
        app = _CapturingApp()
        rtl_programming_simulation.register(app)
        assert app.functions == {}, (
            "with the simulator off there must be no callback that could "
            "reach SimulatorTransport at all"
        )

    def test_the_callback_registers_when_enabled(self, monkeypatch):
        with _simulation_enabled(monkeypatch):
            app = _CapturingApp()
            rtl_programming_simulation.register(app)
        assert "simulate_program_rtl_execution" in app.functions


# ---------------------------------------------------------------------------
# Callback authorization and tamper protection — spied, no database
# ---------------------------------------------------------------------------

DEVICE_ID = "sim-p1-t1-d1"
OTHER_DEVICE_ID = "sim-p1-t1-d2"
REQUEST_ID = 4242


class _Spy:
    def __init__(self, return_value=None):
        self.calls = []
        self.return_value = return_value

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.return_value


class _FakeCommand:
    state = command_cfg.STATE_SUCCEEDED
    failure_code = None


def _request_row(device_id=DEVICE_ID, status="successful"):
    class _Row:
        pass

    row = _Row()
    row.device_id = device_id
    row.status = status
    return row


@pytest.fixture
def handler(monkeypatch):
    """The registered simulation callback plus its spied collaborators."""
    monkeypatch.setattr(
        settings, "programming_simulator", ProgrammingSimulatorSettings(enabled=True)
    )
    monkeypatch.setattr(settings, "IS_PRODUCTION", False)

    simulate = _Spy(return_value=_FakeCommand())
    monkeypatch.setattr(simulation, "simulate_request_execution", simulate)

    lookups = []

    def _get_request(request_id):
        lookups.append(request_id)
        return _request_row() if request_id == REQUEST_ID else None

    monkeypatch.setattr(repo, "get_programming_request", _get_request)
    monkeypatch.setattr(
        repo, "list_active_device_ids_for_user",
        lambda user_id: frozenset({DEVICE_ID}),
    )

    app = _CapturingApp()
    rtl_programming_simulation.register(app)
    return app.functions["simulate_program_rtl_execution"], simulate, lookups


def _rendered(node) -> str:
    return str(node)


def _is_refusal(node) -> bool:
    return ACTION_REFUSED_CLASS in _rendered(node)


class TestSimulationAuthorization:
    def test_administrator_may_simulate_any_rtl(self, handler, monkeypatch):
        run, simulate, _lookups = handler
        with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
            result = run(1, DEVICE_ID, REQUEST_ID, OUTCOME_SUCCESS)
        assert simulate.calls == [
            {"request_id": REQUEST_ID, "outcome": OUTCOME_SUCCESS}
        ]
        assert not _is_refusal(result)

    def test_assigned_technician_may_simulate_their_own_rtl(
        self, handler, monkeypatch
    ):
        run, simulate, _lookups = handler
        with trusted_session(monkeypatch, user_id=2, role=TECHNICIAN):
            result = run(1, DEVICE_ID, REQUEST_ID, OUTCOME_SUCCESS)
        assert simulate.calls, "an assigned technician holds PROGRAM_RTL here"
        assert not _is_refusal(result)

    def test_unassigned_technician_is_refused_before_execution(
        self, handler, monkeypatch
    ):
        run, simulate, lookups = handler
        monkeypatch.setattr(
            repo, "list_active_device_ids_for_user", lambda user_id: frozenset()
        )
        with trusted_session(monkeypatch, user_id=2, role=TECHNICIAN):
            result = run(1, DEVICE_ID, REQUEST_ID, OUTCOME_SUCCESS)
        assert simulate.calls == []
        assert lookups == [], (
            "an unauthorized caller must not reach the request lookup either — "
            "it would leak whether the id exists"
        )
        assert _is_refusal(result)

    def test_general_user_is_refused_before_execution(self, handler, monkeypatch):
        run, simulate, lookups = handler
        with trusted_session(monkeypatch, user_id=3, role=GENERAL):
            result = run(1, DEVICE_ID, REQUEST_ID, OUTCOME_SUCCESS)
        assert simulate.calls == []
        assert lookups == []
        assert _is_refusal(result)

    def test_no_trusted_session_is_refused_before_execution(self, handler):
        run, simulate, lookups = handler
        with no_trusted_session():
            result = run(1, DEVICE_ID, REQUEST_ID, OUTCOME_SUCCESS)
        assert simulate.calls == []
        assert lookups == []
        assert _is_refusal(result)

    def test_hiding_the_control_is_not_the_protection(self, handler, monkeypatch):
        """The refusal above happens inside the callback, so a fabricated
        click against a control that was never rendered is still refused."""
        run, simulate, _lookups = handler
        with trusted_session(monkeypatch, user_id=3, role=GENERAL):
            run(1, DEVICE_ID, REQUEST_ID, OUTCOME_SUCCESS)
        assert simulate.calls == []

    def test_a_press_with_no_clicks_does_nothing(self, handler, monkeypatch):
        run, simulate, _lookups = handler
        with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
            assert run(0, DEVICE_ID, REQUEST_ID, OUTCOME_SUCCESS) is no_update
        assert simulate.calls == []

    def test_an_unselected_outcome_is_a_friendly_refusal_not_a_crash(
        self, handler, monkeypatch
    ):
        """The dropdown is `clearable=False` with a default, so this should
        be unreachable from the UI — it must still refuse rather than raise
        into the browser if the value arrives empty anyway."""
        run, _simulate, _lookups = handler

        def _reject(**kwargs):
            raise simulation.SimulationOutcomeError("no outcome")

        monkeypatch.setattr(simulation, "simulate_request_execution", _reject)
        with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
            result = run(1, DEVICE_ID, REQUEST_ID, None)
        assert "Select a simulated outcome first." in _rendered(result)


class TestUntrustedRequestId:
    def test_a_request_belonging_to_another_device_is_refused(
        self, handler, monkeypatch
    ):
        """The store is browser-owned. Authorization was granted for
        DEVICE_ID, so a request that belongs to a different device must not
        execute — even for an administrator who could have simulated it via
        its own device's drawer."""
        run, simulate, _lookups = handler
        monkeypatch.setattr(
            repo,
            "get_programming_request",
            lambda request_id: _request_row(device_id=OTHER_DEVICE_ID),
        )
        with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
            result = run(1, DEVICE_ID, REQUEST_ID, OUTCOME_SUCCESS)
        assert simulate.calls == []
        assert "No recorded programming request for this RTL" in _rendered(result)

    def test_an_unknown_request_id_is_refused(self, handler, monkeypatch):
        run, simulate, _lookups = handler
        with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
            result = run(1, DEVICE_ID, 999999, OUTCOME_SUCCESS)
        assert simulate.calls == []
        assert "No recorded programming request for this RTL" in _rendered(result)

    def test_unknown_and_mismatched_refusals_are_indistinguishable(
        self, handler, monkeypatch
    ):
        """No request-existence oracle: a browser must not be able to learn
        which request ids exist by comparing the two refusals."""
        run, _simulate, _lookups = handler
        with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
            unknown = _rendered(run(1, DEVICE_ID, 999999, OUTCOME_SUCCESS))
            monkeypatch.setattr(
                repo,
                "get_programming_request",
                lambda request_id: _request_row(device_id=OTHER_DEVICE_ID),
            )
            mismatched = _rendered(run(1, DEVICE_ID, REQUEST_ID, OUTCOME_SUCCESS))
        assert unknown == mismatched

    @pytest.mark.parametrize("tampered", [None, "4242", True, 4.0, {"id": 1}, []])
    def test_a_non_integer_request_id_is_refused_before_any_lookup(
        self, handler, monkeypatch, tampered
    ):
        run, simulate, lookups = handler
        with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
            result = run(1, DEVICE_ID, tampered, OUTCOME_SUCCESS)
        assert simulate.calls == []
        assert lookups == []
        assert "No recorded programming request for this RTL" in _rendered(result)

    def test_a_missing_device_id_is_refused_before_any_lookup(
        self, handler, monkeypatch
    ):
        """With no device on the drawer there is nothing an ownership check
        could compare against, so nothing may execute."""
        run, simulate, lookups = handler
        with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
            result = run(1, None, REQUEST_ID, OUTCOME_SUCCESS)
        assert simulate.calls == []
        assert lookups == []
        assert "No recorded programming request for this RTL" in _rendered(result)

    def test_the_refusal_echoes_no_device_or_request_detail(
        self, handler, monkeypatch
    ):
        run, _simulate, _lookups = handler
        monkeypatch.setattr(
            repo,
            "get_programming_request",
            lambda request_id: _request_row(device_id=OTHER_DEVICE_ID),
        )
        with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
            rendered = _rendered(run(1, DEVICE_ID, REQUEST_ID, OUTCOME_SUCCESS))
        assert OTHER_DEVICE_ID not in rendered


# ---------------------------------------------------------------------------
# Structural boundary — who may construct a SimulatorTransport
# ---------------------------------------------------------------------------


def _imported_names(module) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


class TestSimulatorTransportBoundary:
    def test_the_normal_execution_service_still_does_not_import_the_simulator(self):
        """RTL-PROG-EXEC-1's seam stays protocol-neutral: the production
        execution path must never gain a default transport."""
        names = _imported_names(execution)
        assert "SimulatorTransport" not in names
        assert not any("simulator" in name.lower() for name in names)

    def test_the_programming_service_does_not_import_the_simulator(self):
        names = _imported_names(prog)
        assert not any("simulator" in name.lower() for name in names)

    def test_the_production_manage_callbacks_do_not_import_the_simulator(self):
        """`callbacks/device_manage.py` records requests; it must not be able
        to execute one through a simulated transport."""
        names = _imported_names(device_manage)
        assert "SimulatorTransport" not in names
        assert not any("simulator" in name.lower() for name in names)

    def test_only_the_simulation_service_constructs_a_simulator_transport(self):
        """One module may name `SimulatorTransport(...)`, and it is the one
        that checks enablement first."""
        names = _imported_names(simulation)
        assert "SimulatorTransport" in names

    def test_the_simulation_service_delegates_rather_than_reimplementing(self):
        """No lifecycle logic may be duplicated here — it must call the
        existing execution seam."""
        source = inspect.getsource(simulation)
        assert "execute_request" in source
        for lifecycle_call in (
            "mark_sent", "mark_acknowledged", "mark_succeeded",
            "mark_failed", "mark_timed_out", "update_command_state",
            "update_programming_request_status", "dispatch_command",
        ):
            assert lifecycle_call not in source, (
                f"{lifecycle_call} must stay in the existing lifecycle layer"
            )


# ---------------------------------------------------------------------------
# Database-backed — the simulated outcomes actually reaching the request
# ---------------------------------------------------------------------------

DB_DEVICE_ID = "simx-p1-t1-d1"
DB_OTHER_DEVICE_ID = "simx-p1-t1-d2"
DB_TRANSFORMER_ID = "simx-p1-t1"


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
                "VALUES ('simx-p1', 'Sim Plant', 'Testland', 0, 0)"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES ('{DB_TRANSFORMER_ID}', 'simx-p1', 't1')"
            )
        )
        for device_id, code in ((DB_DEVICE_ID, "29001"), (DB_OTHER_DEVICE_ID, "29002")):
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.devices "
                    f"(device_id, transformer_id, device_code) "
                    f"VALUES ('{device_id}', '{DB_TRANSFORMER_ID}', '{code}')"
                )
            )


def _status_row(request_id: int) -> dict:
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
class TestSimulatedOutcomesAgainstTheDatabase:
    def setup_method(self):
        _wipe()
        _seed_hierarchy()
        self.admin = repo.create_or_update_user(
            username="sim-admin", full_name="Sim Admin",
            role="administrator", status="active",
        ).user_id

    def _record(self, device_id=DB_DEVICE_ID):
        return prog.record_request(
            device_id=device_id, master_msisdn="0700000000",
            actor_user_id=self.admin,
        )

    def test_recording_a_request_executes_nothing(self, monkeypatch):
        """The simulation is never automatic: a recorded request is queued
        and its command untouched until someone explicitly simulates."""
        record = self._record()

        command = cmd.get_command_for_request(record.request_id)
        assert command.state == command_cfg.STATE_QUEUED
        assert command.sent_at is None
        assert _status_row(record.request_id)["status"] == (
            command_cfg.REQUEST_STATUS_QUEUED
        )

    def test_success_projects_the_request_successful(self, monkeypatch):
        record = self._record()
        with _simulation_enabled(monkeypatch):
            command = simulation.simulate_request_execution(
                request_id=record.request_id, outcome=OUTCOME_SUCCESS
            )

        assert command.state == command_cfg.STATE_SUCCEEDED
        row = _status_row(record.request_id)
        assert row["status"] == command_cfg.REQUEST_STATUS_SUCCESSFUL
        assert row["completed_at"] is not None
        assert row["error_message"] is None

    def test_failure_projects_the_request_failed_with_a_simulated_code(
        self, monkeypatch
    ):
        record = self._record()
        with _simulation_enabled(monkeypatch):
            command = simulation.simulate_request_execution(
                request_id=record.request_id, outcome=OUTCOME_FAILURE
            )

        assert command.state == command_cfg.STATE_FAILED
        row = _status_row(record.request_id)
        assert row["status"] == command_cfg.REQUEST_STATUS_FAILED
        assert row["completed_at"] is not None
        assert command_cfg.FAILURE_CODE_SIMULATED_FAILURE in row["error_message"]
        assert "Simulated" in row["error_message"]

    def test_timeout_projects_the_request_failed_with_a_simulated_timeout(
        self, monkeypatch
    ):
        record = self._record()
        with _simulation_enabled(monkeypatch):
            command = simulation.simulate_request_execution(
                request_id=record.request_id, outcome=OUTCOME_TIMEOUT
            )

        assert command.state == command_cfg.STATE_TIMED_OUT
        row = _status_row(record.request_id)
        assert row["status"] == command_cfg.REQUEST_STATUS_FAILED
        assert command_cfg.FAILURE_CODE_SIMULATED_TIMEOUT in row["error_message"]

    def test_repeated_simulation_is_refused_by_the_existing_lifecycle(
        self, monkeypatch
    ):
        record = self._record()
        with _simulation_enabled(monkeypatch):
            simulation.simulate_request_execution(
                request_id=record.request_id, outcome=OUTCOME_SUCCESS
            )
            before = _status_row(record.request_id)

            with pytest.raises(execution.ProgrammingExecutionError):
                simulation.simulate_request_execution(
                    request_id=record.request_id, outcome=OUTCOME_FAILURE
                )

        assert _status_row(record.request_id) == before, (
            "a refused re-run must not overwrite the recorded outcome"
        )

    def test_a_disabled_simulator_executes_nothing_against_the_database(self):
        record = self._record()

        with pytest.raises(simulation.SimulationDisabledError):
            simulation.simulate_request_execution(
                request_id=record.request_id, outcome=OUTCOME_SUCCESS
            )

        assert cmd.get_command_for_request(record.request_id).state == (
            command_cfg.STATE_QUEUED
        )
        assert _status_row(record.request_id)["status"] == (
            command_cfg.REQUEST_STATUS_QUEUED
        )

    def test_a_mismatched_request_id_never_executes_the_other_devices_request(
        self, monkeypatch
    ):
        """End-to-end tamper proof: the callback is handed a real request id
        belonging to a DIFFERENT device, and that device's command must stay
        QUEUED."""
        mine = self._record(DB_DEVICE_ID)
        theirs = self._record(DB_OTHER_DEVICE_ID)

        with _simulation_enabled(monkeypatch):
            app = _CapturingApp()
            rtl_programming_simulation.register(app)
            run = app.functions["simulate_program_rtl_execution"]

            with trusted_session(monkeypatch, user_id=self.admin, role=ADMINISTRATOR):
                result = run(1, DB_DEVICE_ID, theirs.request_id, OUTCOME_SUCCESS)

        assert "No recorded programming request for this RTL" in str(result)
        assert cmd.get_command_for_request(theirs.request_id).state == (
            command_cfg.STATE_QUEUED
        )
        assert _status_row(theirs.request_id)["status"] == (
            command_cfg.REQUEST_STATUS_QUEUED
        )
        assert cmd.get_command_for_request(mine.request_id).state == (
            command_cfg.STATE_QUEUED
        )

    def test_the_callback_reports_the_simulated_status_honestly(self, monkeypatch):
        record = self._record()

        with _simulation_enabled(monkeypatch):
            app = _CapturingApp()
            rtl_programming_simulation.register(app)
            run = app.functions["simulate_program_rtl_execution"]

            with trusted_session(monkeypatch, user_id=self.admin, role=ADMINISTRATOR):
                result = run(1, DB_DEVICE_ID, record.request_id, OUTCOME_SUCCESS)

        rendered = str(result)
        assert command_cfg.REQUEST_STATUS_SUCCESSFUL in rendered
        assert drawer.SIMULATION_NOTICE in rendered
        assert "not evidence that the physical" in rendered
