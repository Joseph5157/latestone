"""Isolated-schema data-scope tests for the Administrator audit-log viewer."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from db.engine import session_scope
from repositories import plant_monitoring_repository as repo


pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]


@pytest.fixture(autouse=True)
def _audit_rows(isolated_schema: str):
    with session_scope() as session:
        session.execute(text(f"DELETE FROM {isolated_schema}.audit_log"))
        session.execute(text(f"DELETE FROM {isolated_schema}.users"))
        actor_id = session.execute(
            text(
                f"INSERT INTO {isolated_schema}.users "
                "(username, full_name, role) "
                "VALUES ('audit-actor', 'Audit Actor', 'administrator') "
                "RETURNING user_id"
            )
        ).scalar_one()
        session.execute(
            text(
                f"INSERT INTO {isolated_schema}.audit_log "
                "(user_id, operation, entity_type, entity_id, occurred_at) "
                "VALUES (:actor_id, 'USER_UPDATED', 'user', 'audit-actor', :older), "
                "(NULL, 'AUTO_DISABLE_APPLIED', 'message_forwarding', 'global', :newer)"
            ),
            {
                "actor_id": actor_id,
                "older": datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc),
                "newer": datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc),
            },
        )


def test_list_audit_log_is_newest_first_and_keeps_system_rows():
    records = repo.list_audit_log(limit=10)

    assert [(record.operation, record.actor_name) for record in records] == [
        ("AUTO_DISABLE_APPLIED", "System"),
        ("USER_UPDATED", "Audit Actor"),
    ]


def test_list_audit_log_returns_only_safe_viewer_fields():
    record = repo.list_audit_log(limit=1)[0]

    assert set(record.__dataclass_fields__) == {
        "audit_id", "occurred_at", "actor_name", "operation", "entity_type", "entity_id"
    }


@pytest.mark.parametrize("limit", [0, -1, True, "10"])
def test_list_audit_log_rejects_invalid_limits(limit):
    with pytest.raises(ValueError):
        repo.list_audit_log(limit=limit)
