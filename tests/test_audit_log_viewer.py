"""Pure authorization and presentation tests for the audit-log viewer."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from callbacks import audit_log as callback
from pages import audit_log as page
from repositories.plant_monitoring_repository import AuditLogRecord
from routes import parse_pathname
from services import audit_log_service
from services.auth_service import AuthenticatedUser
from services.authorization import (
    ADMINISTRATOR,
    GENERAL,
    TECHNICIAN,
    AuthorizationError,
    VIEW_AUDIT_LOG,
    may_perform_capability,
)
from tests.dash_tree import text_of


NOW = datetime(2026, 9, 16, 10, 30, tzinfo=timezone.utc)


def _user(role: str) -> AuthenticatedUser:
    return AuthenticatedUser(7, "operator", "Operator", role)


def _record(*, actor_name: str = "Operator") -> AuditLogRecord:
    return AuditLogRecord(
        audit_id=12,
        occurred_at=NOW,
        actor_name=actor_name,
        operation="DEVICE_ASSIGNED",
        entity_type="device_assignment",
        entity_id="plant-01-t1-d1",
    )


class TestAuditLogAuthorization:
    def test_admin_route_and_capability_are_administrator_only(self):
        assert parse_pathname("/admin/audit-log").name == "audit_log"
        assert may_perform_capability(ADMINISTRATOR, VIEW_AUDIT_LOG)
        assert not may_perform_capability(TECHNICIAN, VIEW_AUDIT_LOG)
        assert not may_perform_capability(GENERAL, VIEW_AUDIT_LOG)

    @pytest.mark.parametrize("role", [TECHNICIAN, GENERAL])
    def test_refused_role_cannot_start_audit_read(self, monkeypatch, role):
        reads = []
        monkeypatch.setattr(
            callback.audit_log_service,
            "recent_audit_log",
            lambda: reads.append(True),
        )

        with pytest.raises(AuthorizationError):
            callback.audit_log_outputs(_user(role))

        assert reads == []

    def test_admin_read_uses_existing_read_only_service(self, monkeypatch):
        monkeypatch.setattr(
            callback.audit_log_service,
            "recent_audit_log",
            lambda: [_record()],
        )

        rows, _columns, error, summary = callback.audit_log_outputs(_user(ADMINISTRATOR))

        assert rows[0]["actor"] == "Operator"
        assert error is None
        assert summary == "Showing 1 newest audit record"


class TestAuditLogPresentation:
    def test_rows_expose_only_the_requested_safe_fields(self):
        row = callback.audit_log_rows([_record(actor_name="System")])[0]

        assert row == {
            "id": 12,
            "occurred_at": "2026-09-16 10:30 UTC",
            "actor": "System",
            "operation": "DEVICE_ASSIGNED",
            "entity_type": "device_assignment",
            "entity_id": "plant-01-t1-d1",
        }

    def test_layout_is_explicitly_read_only_and_has_no_mutation_controls(self):
        rendered = text_of(page.layout()).lower()
        assert "read-only" in rendered
        assert "cannot be changed here" in rendered
        assert "delete" not in rendered
        assert "edit" not in rendered

    def test_service_wraps_repository_failures_in_a_safe_error(self, monkeypatch):
        def _explode(**_kwargs):
            raise RuntimeError("database detail")

        monkeypatch.setattr(audit_log_service.repo, "list_audit_log", _explode)
        with pytest.raises(audit_log_service.AuditLogViewerError) as exc_info:
            audit_log_service.recent_audit_log()

        assert "database detail" not in str(exc_info.value)
