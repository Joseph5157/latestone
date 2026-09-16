"""RTL-PROG-VIS-1: scope-safe, truthful programming history visibility."""
from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from callbacks import programming_activity as activity_callback
from components.programming_activity import (
    PROGRAMMING_ACTIVITY_ID,
    programming_activity_panel,
)
from config import commands as command_cfg
from repositories import plant_monitoring_repository as repo
from db.engine import session_scope
from services import rtl_programming_activity_service as activity_service
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN
from services.device_scope import DeviceScope, UNRESTRICTED
from tests.auth_test_support import as_session
from tests.dash_tree import find_by_class, find_by_exact_class, find_by_id, text_of

NOW = datetime(2026, 9, 15, 14, 32, tzinfo=timezone.utc)
DEVICE_ID = "plant-01-t1-d1"
OTHER_DEVICE_ID = "plant-02-t1-d1"

ADMIN_SESSION = {
    "authenticated": True,
    "user_id": 1,
    "username": "admin",
    "full_name": "Admin",
    "role": ADMINISTRATOR,
}
TECH_SESSION = {
    "authenticated": True,
    "user_id": 2,
    "username": "tech",
    "full_name": "Tech",
    "role": TECHNICIAN,
}
GENERAL_SESSION = {
    "authenticated": True,
    "user_id": 3,
    "username": "general",
    "full_name": "General",
    "role": GENERAL,
}


def _record(
    *,
    request_id: int = 42,
    requested_at: datetime = NOW,
    request_status: str = command_cfg.REQUEST_STATUS_QUEUED,
    command_state: str | None = command_cfg.STATE_QUEUED,
    error_message: str | None = None,
) -> repo.ProgrammingActivityRecord:
    return repo.ProgrammingActivityRecord(
        request_id=request_id,
        device_id=DEVICE_ID,
        requested_by_name="Technician One",
        master_msisdn="+27123456789",
        requested_at=requested_at,
        request_status=request_status,
        request_completed_at=None,
        error_message=error_message,
        command_id=9 if command_state else None,
        command_type=command_cfg.COMMAND_TYPE_PROGRAM_RTL if command_state else None,
        command_state=command_state,
        command_sent_at=None,
        command_acknowledged_at=None,
        command_completed_at=None,
        failure_code=None,
    )


class _CapturingApp:
    def __init__(self):
        self.functions = {}
        self.specs = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions[fn.__name__] = fn
            self.specs[fn.__name__] = (args, kwargs)
            return fn
        return decorator


def _handler():
    app = _CapturingApp()
    activity_callback.register(app)
    return app.functions["render_programming_activity"]


class TestActivityPresentation:
    def test_empty_history_is_a_truthful_first_use_state(self):
        rendered = text_of(programming_activity_panel([]))
        assert "No programming activity recorded for this RTL." in rendered
        assert "never been programmed" not in rendered.lower()

    def test_queued_request_is_presented_as_recorded_not_delivered(self):
        rendered = text_of(programming_activity_panel([_record()])).lower()
        assert "queued" in rendered
        assert "request recorded; command is queued" in rendered
        assert "awaiting device integration" in rendered
        assert "requested technician one" not in rendered
        assert "requested " in rendered

    def test_simulated_success_is_explicitly_identified(self):
        record = _record(
            request_status=command_cfg.REQUEST_STATUS_SUCCESSFUL,
            command_state=command_cfg.STATE_SUCCEEDED,
        )
        rendered = text_of(programming_activity_panel([record])).lower()
        assert "completed in simulation" in rendered
        assert "succeeded" in rendered
        assert "simulation (development only)" in rendered
        assert "no physical rtl delivery occurred" in rendered

    def test_failed_and_timed_out_commands_use_safe_operational_wording(self):
        failed = _record(
            request_status=command_cfg.REQUEST_STATUS_FAILED,
            command_state=command_cfg.STATE_FAILED,
            error_message="SIMULATED_FAILURE: configured failure",
        )
        timed_out = _record(
            request_id=41,
            request_status=command_cfg.REQUEST_STATUS_FAILED,
            command_state=command_cfg.STATE_TIMED_OUT,
        )
        rendered = text_of(programming_activity_panel([failed, timed_out])).lower()
        assert "simulated_failure: configured failure" in rendered
        assert "timed out" in rendered
        assert "simulation timed out before completion" in rendered

    def test_no_copy_implies_physical_delivery(self):
        rendered = text_of(programming_activity_panel([_record(
            request_status=command_cfg.REQUEST_STATUS_SUCCESSFUL,
            command_state=command_cfg.STATE_SUCCEEDED,
        )])).lower()
        for forbidden in (
            "programmed successfully",
            "delivered to rtl",
            "device confirmed",
            "physical device execution",
        ):
            assert forbidden not in rendered

    def test_command_and_audit_history_use_safe_read_only_labels(self):
        audit = repo.DeviceAuditHistoryRecord(
            audit_id=7,
            device_id=DEVICE_ID,
            occurred_at=NOW,
            operation="RTL_PROGRAM_REQUESTED",
            requester_name="Technician One",
        )
        rendered = text_of(programming_activity_panel([_record()], [audit])).lower()
        assert "command & audit history" in rendered
        assert "program rtl" in rendered
        assert "rtl program requested" in rendered
        assert "technician one" in rendered

    def test_device_dashboard_carries_a_loading_activity_slot(self):
        from pages.device_dashboard import layout

        assert find_by_id(layout(), PROGRAMMING_ACTIVITY_ID) is not None


class TestLifecycleRail:
    """MOBBIN-UX-1: the discrete Program RTL lifecycle rail.

    Named states only, backed by the real `rtl_commands` transition map
    (`config/commands.py`). No percentage, no animation classes, and a
    FAILED/TIMED_OUT outcome must truncate the rail truthfully rather than
    showing ACKNOWLEDGED/SUCCEEDED as still reachable.
    """

    def test_queued_shows_current_step_and_awaiting_integration(self):
        rendered = text_of(programming_activity_panel([_record(
            command_state=command_cfg.STATE_QUEUED,
        )])).lower()
        assert "queued (current)" in rendered
        assert "sent (awaiting device integration)" in rendered
        assert "acknowledged (not yet reached)" in rendered
        assert "succeeded (not yet reached)" in rendered

    def test_sent_shows_queued_done_and_sent_current(self):
        rendered = text_of(programming_activity_panel([_record(
            request_status=command_cfg.REQUEST_STATUS_SENT,
            command_state=command_cfg.STATE_SENT,
        )])).lower()
        assert "queued (done)" in rendered
        assert "sent (current)" in rendered
        assert "acknowledged (not yet reached)" in rendered
        assert "succeeded (not yet reached)" in rendered

    def test_acknowledged_shows_two_done_steps_and_current(self):
        rendered = text_of(programming_activity_panel([_record(
            request_status=command_cfg.REQUEST_STATUS_SENT,
            command_state=command_cfg.STATE_ACKNOWLEDGED,
        )])).lower()
        assert "queued (done)" in rendered
        assert "sent (done)" in rendered
        assert "acknowledged (current)" in rendered
        assert "succeeded (not yet reached)" in rendered

    def test_succeeded_shows_every_step_resolved(self):
        rendered = text_of(programming_activity_panel([_record(
            request_status=command_cfg.REQUEST_STATUS_SUCCESSFUL,
            command_state=command_cfg.STATE_SUCCEEDED,
        )])).lower()
        assert "queued (done)" in rendered
        assert "sent (done)" in rendered
        assert "acknowledged (done)" in rendered
        assert "succeeded (completed)" in rendered

    def test_failed_terminates_the_rail_after_sent(self):
        rendered = text_of(programming_activity_panel([_record(
            request_status=command_cfg.REQUEST_STATUS_FAILED,
            command_state=command_cfg.STATE_FAILED,
            error_message="SIMULATED_FAILURE: configured failure",
        )])).lower()
        assert "queued (done)" in rendered
        assert "sent (done)" in rendered
        assert "failed (command did not complete)" in rendered
        assert "acknowledged" not in rendered
        assert "succeeded" not in rendered

    def test_timed_out_terminates_the_rail_after_sent(self):
        rendered = text_of(programming_activity_panel([_record(
            request_status=command_cfg.REQUEST_STATUS_FAILED,
            command_state=command_cfg.STATE_TIMED_OUT,
        )])).lower()
        assert "queued (done)" in rendered
        assert "sent (done)" in rendered
        assert "timed out (command did not complete)" in rendered
        assert "acknowledged" not in rendered
        assert "succeeded" not in rendered

    def test_no_command_record_renders_a_single_truthful_placeholder(self):
        rendered = text_of(programming_activity_panel([_record(
            request_status=command_cfg.REQUEST_STATUS_PENDING,
            command_state=None,
        )])).lower()
        assert "no command record" in rendered
        for state_word in ("queued", "sent", "acknowledged", "succeeded", "timed out"):
            assert state_word not in rendered

    def test_rail_never_renders_percentage_progress(self):
        for state in (
            command_cfg.STATE_QUEUED,
            command_cfg.STATE_SENT,
            command_cfg.STATE_ACKNOWLEDGED,
            command_cfg.STATE_SUCCEEDED,
            command_cfg.STATE_FAILED,
            command_cfg.STATE_TIMED_OUT,
        ):
            rendered = text_of(programming_activity_panel([_record(command_state=state)]))
            assert "%" not in rendered

    def test_rail_markers_are_decorative_only(self):
        from components.programming_activity import _lifecycle_rail

        rail = _lifecycle_rail(_record(command_state=command_cfg.STATE_QUEUED))
        marker = rail.children[0].children[0]
        assert getattr(marker, "aria-hidden") == "true"


class TestCompactAuditHistory:
    """MOBBIN-UX-5: audit history renders as a compact reverse-chronological
    log — a decorative marker, the action, then "Requester · Timestamp" —
    never the command list's larger card treatment, and never a severity
    class on the marker (audit actions carry no severity)."""

    def _audit(
        self, *, audit_id=7, operation="RTL_PROGRAM_REQUESTED",
        requester="Technician One", occurred_at=NOW,
    ):
        return repo.DeviceAuditHistoryRecord(
            audit_id=audit_id,
            device_id=DEVICE_ID,
            occurred_at=occurred_at,
            operation=operation,
            requester_name=requester,
        )

    def test_action_renders(self):
        """1. The operation, title-cased, is present."""
        rendered = text_of(programming_activity_panel([], [self._audit()]))
        assert "Rtl Program Requested" in rendered

    def test_requester_renders(self):
        """2. The exact requester_name the read model supplied is present."""
        rendered = text_of(programming_activity_panel(
            [], [self._audit(requester="Technician One")]
        ))
        assert "Technician One" in rendered

    def test_timestamp_renders(self):
        """3. The exact occurred_at timestamp, formatted the same way the
        command list already formats every other timestamp on this panel."""
        from components.programming_activity import _timestamp

        rendered = text_of(programming_activity_panel([], [self._audit(occurred_at=NOW)]))
        assert _timestamp(NOW) in rendered

    def test_audit_records_remain_in_supplied_order(self):
        """4. This component renders order as given — it does not re-sort.
        Ordering itself is the repository/service's job
        (`list_device_audit_history`'s `ORDER BY ... DESC`), asserted
        separately in TestScopedReader below."""
        newest = self._audit(audit_id=2, operation="RTL_DEACTIVATED", requester="Bob")
        oldest = self._audit(audit_id=1, operation="RTL_PROGRAM_REQUESTED", requester="Alice")

        panel = programming_activity_panel([], [newest, oldest])
        actions = [text_of(n) for n in find_by_exact_class(panel, "programming-activity__audit-action")]
        assert actions == ["Rtl Deactivated", "Rtl Program Requested"]

    def test_redundant_filler_labels_are_gone(self):
        """5. The old per-row "Lifecycle: Audit record" / "Execution: Not
        applicable" / "Result: Recorded in this application" rows added no
        fact beyond "this is an audit entry" and must not render."""
        rendered = text_of(programming_activity_panel([], [self._audit()])).lower()
        assert "lifecycle: audit record" not in rendered
        assert "execution: not applicable" not in rendered
        assert "result: recorded in this application" not in rendered
        assert "not applicable" not in rendered
        assert "recorded in this application" not in rendered
        # The compact row also carries no per-entry detail grid at all.
        audit_item = find_by_exact_class(
            programming_activity_panel([], [self._audit()]),
            "programming-activity__audit-item",
        )[0]
        assert find_by_class(audit_item, "programming-activity__detail") == []

    def test_command_lifecycle_rendering_is_unchanged(self):
        """6. This tranche touches audit presentation only — the command
        history rail keeps its exact existing markup and wording."""
        rendered = text_of(programming_activity_panel([_record()], [])).lower()
        assert "queued (current)" in rendered
        assert "awaiting device integration" in rendered
        assert find_by_class(
            programming_activity_panel([_record()], []),
            "programming-activity__lifecycle",
        )

    def test_empty_audit_state_is_unchanged(self):
        """7. Zero audit records still renders the same truthful empty-state
        sentence, not the compact list markup."""
        panel = programming_activity_panel([], [])
        rendered = text_of(panel)
        assert "No audit activity recorded for this RTL." in rendered
        assert find_by_class(panel, "programming-activity__audit-item") == []


class TestScopedReader:
    def test_assigned_device_reaches_the_batched_repository_reader(self, monkeypatch):
        calls = []
        expected = [_record()]
        monkeypatch.setattr(
            activity_service.repo,
            "list_programming_activity",
            lambda ids, **kwargs: calls.append((ids, kwargs)) or expected,
        )
        scope = DeviceScope(frozenset({DEVICE_ID}))

        assert activity_service.recent_activity(DEVICE_ID, scope=scope) == expected
        assert calls == [(
            [DEVICE_ID],
            {"allowed_device_ids": scope.device_ids, "limit_per_device": 10},
        )]

    def test_unassigned_device_returns_empty_without_a_repository_read(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            activity_service.repo,
            "list_programming_activity",
            lambda *args, **kwargs: calls.append((args, kwargs)),
        )

        assert activity_service.recent_activity(
            OTHER_DEVICE_ID, scope=DeviceScope(frozenset({DEVICE_ID}))
        ) == []
        assert calls == []

    def test_unassigned_device_cannot_read_audit_history(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            activity_service.repo,
            "list_device_audit_history",
            lambda *args, **kwargs: calls.append((args, kwargs)),
        )

        assert activity_service.recent_audit_history(
            OTHER_DEVICE_ID, scope=DeviceScope(frozenset({DEVICE_ID}))
        ) == []
        assert calls == []

    def test_assigned_device_reaches_the_scoped_audit_reader(self, monkeypatch):
        calls = []
        expected = [
            repo.DeviceAuditHistoryRecord(
                audit_id=7,
                device_id=DEVICE_ID,
                occurred_at=NOW,
                operation="RTL_PROGRAM_REQUESTED",
                requester_name="Technician One",
            )
        ]
        monkeypatch.setattr(
            activity_service.repo,
            "list_device_audit_history",
            lambda ids, **kwargs: calls.append((ids, kwargs)) or expected,
        )
        scope = DeviceScope(frozenset({DEVICE_ID}))

        assert activity_service.recent_audit_history(DEVICE_ID, scope=scope) == expected
        assert calls == [(
            [DEVICE_ID],
            {"allowed_device_ids": scope.device_ids, "limit_per_device": 10},
        )]

    def test_repository_reader_is_batched_scoped_and_newest_first(self):
        source = inspect.getsource(repo.list_programming_activity)
        assert "ROW_NUMBER() OVER" in source
        assert "PARTITION BY r.device_id" in source
        assert "ORDER BY r.requested_at DESC, r.request_id DESC" in source
        assert "allowed_device_ids" in source
        assert "LEFT JOIN" in source

    def test_audit_repository_reader_is_batched_scoped_and_newest_first(self):
        source = inspect.getsource(repo.list_device_audit_history)
        assert "JOIN" in source
        assert "a.entity_type = 'device'" in source
        assert "ROW_NUMBER() OVER" in source
        assert "ORDER BY a.occurred_at DESC, a.audit_id DESC" in source
        assert "allowed_device_ids" in source


class TestTrustedScopeCallback:
    def _call(self, monkeypatch, session, scope, device_id=DEVICE_ID, auth_data=None):
        monkeypatch.setattr(activity_callback, "current_device_scope", lambda: scope)
        return_value = [_record()]
        calls = []
        monkeypatch.setattr(
            activity_callback.activity_service,
            "recent_activity",
            lambda target, *, scope: calls.append((target, scope)) or return_value,
        )
        monkeypatch.setattr(
            activity_callback.activity_service,
            "recent_audit_history",
            lambda target, *, scope: calls.append((f"audit:{target}", scope)) or [],
        )
        with as_session(monkeypatch, session):
            result = _handler()(
                {"route": "device", "device_id": device_id},
                auth_data if auth_data is not None else session,
                None,
            )
        return result, calls

    def test_administrator_can_read_any_rtl_activity(self, monkeypatch):
        result, calls = self._call(monkeypatch, ADMIN_SESSION, UNRESTRICTED)
        assert result is not None
        assert calls == [(DEVICE_ID, UNRESTRICTED), (f"audit:{DEVICE_ID}", UNRESTRICTED)]

    def test_technician_can_read_an_assigned_rtl_activity(self, monkeypatch):
        scope = DeviceScope(frozenset({DEVICE_ID}))
        result, calls = self._call(monkeypatch, TECH_SESSION, scope)
        assert result is not None
        assert calls == [(DEVICE_ID, scope), (f"audit:{DEVICE_ID}", scope)]

    def test_technician_cannot_read_an_unassigned_rtl_activity(self, monkeypatch):
        scope = DeviceScope(frozenset({DEVICE_ID}))
        result, calls = self._call(
            monkeypatch, TECH_SESSION, scope, device_id=OTHER_DEVICE_ID
        )
        assert result is None
        assert calls == []

    def test_general_user_receives_no_programming_activity(self, monkeypatch):
        result, calls = self._call(monkeypatch, GENERAL_SESSION, UNRESTRICTED)
        assert result is None
        assert calls == []

    def test_browser_auth_store_cannot_widen_the_trusted_technician_scope(self, monkeypatch):
        scope = DeviceScope(frozenset({DEVICE_ID}))
        forged_admin_store = {**ADMIN_SESSION, "authenticated": True}
        result, calls = self._call(
            monkeypatch,
            TECH_SESSION,
            scope,
            device_id=OTHER_DEVICE_ID,
            auth_data=forged_admin_store,
        )
        assert result is None
        assert calls == []

    def test_non_device_context_renders_nothing(self, monkeypatch):
        monkeypatch.setattr(activity_callback, "current_device_scope", lambda: UNRESTRICTED)
        with as_session(monkeypatch, ADMIN_SESSION):
            assert _handler()({"route": "overview"}, ADMIN_SESSION, None) is None


def test_existing_program_request_callback_remains_record_only():
    """RTL-PROG-VIS-1 must not turn the existing action into dispatch."""
    from callbacks import device_manage

    app = _CapturingApp()
    device_manage.register(app)
    source = inspect.getsource(app.functions["confirm_program_rtl"])
    assert "record_request" in source
    assert "execute_request" not in source
    assert "dispatch_command" not in source


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestProgrammingActivityRepository:
    """The reader's newest-first and SQL scope behaviour on a real schema."""

    plant_id = "prog-activity-p1"
    transformer_id = "prog-activity-p1-t1"
    device_id = "prog-activity-p1-t1-d1"
    other_device_id = "prog-activity-p1-t1-d2"

    def setup_method(self):
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.plants "
                    "(plant_id, name, country, latitude, longitude) "
                    "VALUES (:id, 'Activity Plant', 'Testland', 0, 0)"
                ),
                {"id": self.plant_id},
            )
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.transformers "
                    "(transformer_id, plant_id, transformer_code) "
                    "VALUES (:id, :plant_id, 'T1')"
                ),
                {"id": self.transformer_id, "plant_id": self.plant_id},
            )
            for device_id, code in ((self.device_id, "D1"), (self.other_device_id, "D2")):
                session.execute(
                    text(
                        f"INSERT INTO {repo._SCHEMA}.devices "
                        "(device_id, transformer_id, device_code) "
                        "VALUES (:id, :transformer_id, :code)"
                    ),
                    {
                        "id": device_id,
                        "transformer_id": self.transformer_id,
                        "code": code,
                    },
                )
        self.actor = repo.create_or_update_user(
            username="prog-activity-actor",
            full_name="Activity Operator",
            role=ADMINISTRATOR,
            status="active",
        )

    def test_scoped_reader_orders_history_and_keeps_unrelated_rtl_out(self):
        oldest = repo.create_programming_request(
            self.device_id,
            master_msisdn="2700000001",
            requested_by=self.actor.user_id,
            request_method="dashboard",
        )
        newest = repo.create_programming_request(
            self.device_id,
            master_msisdn="2700000002",
            requested_by=self.actor.user_id,
            request_method="dashboard",
        )
        other = repo.create_programming_request(
            self.other_device_id,
            master_msisdn="2700000003",
            requested_by=self.actor.user_id,
            request_method="dashboard",
        )
        repo.create_command(
            request_id=newest.request_id,
            command_type=command_cfg.COMMAND_TYPE_PROGRAM_RTL,
            state=command_cfg.STATE_QUEUED,
        )
        with session_scope() as session:
            session.execute(
                text(
                    f"UPDATE {repo._SCHEMA}.rtl_programming_requests "
                    "SET requested_at = :requested_at WHERE request_id = :request_id"
                ),
                {"request_id": oldest.request_id, "requested_at": datetime(2026, 1, 1, tzinfo=timezone.utc)},
            )
            session.execute(
                text(
                    f"UPDATE {repo._SCHEMA}.rtl_programming_requests "
                    "SET requested_at = :requested_at WHERE request_id = :request_id"
                ),
                {"request_id": newest.request_id, "requested_at": datetime(2026, 1, 2, tzinfo=timezone.utc)},
            )

        rows = repo.list_programming_activity(
            [self.device_id, self.other_device_id],
            allowed_device_ids=frozenset({self.device_id}),
            limit_per_device=2,
        )

        assert [row.request_id for row in rows] == [newest.request_id, oldest.request_id]
        assert all(row.device_id == self.device_id for row in rows)
        assert rows[0].requested_by_name == "Activity Operator"
        assert rows[0].command_type == command_cfg.COMMAND_TYPE_PROGRAM_RTL
        assert rows[0].command_state == command_cfg.STATE_QUEUED
        assert other.request_id not in {row.request_id for row in rows}
