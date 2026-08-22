"""Repository-level scope constraint tests.

Runs against a disposable schema — never the developer's real
plant_monitoring.* tables. See tests/conftest.py::isolated_schema.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services.prototype_users import clear_all_users, upsert_user

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]


def _seed_tree(plant_id: str, transformer_id: str, device_ids: list[str]) -> None:
    """Minimal plant/transformer/device rows satisfying the assignment FK."""
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants "
                f"(plant_id, name, country, latitude, longitude) "
                f"VALUES (:plant_id, 'Test Plant', 'Testland', 0, 0) "
                f"ON CONFLICT (plant_id) DO NOTHING"
            ),
            {"plant_id": plant_id},
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES (:transformer_id, :plant_id, 't1') "
                f"ON CONFLICT (transformer_id) DO NOTHING"
            ),
            {"transformer_id": transformer_id, "plant_id": plant_id},
        )
        for device_id in device_ids:
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.devices "
                    f"(device_id, transformer_id, device_code) "
                    f"VALUES (:device_id, :transformer_id, :device_id) "
                    f"ON CONFLICT (device_id) DO NOTHING"
                ),
                {"device_id": device_id, "transformer_id": transformer_id},
            )


def _technician(username: str) -> int:
    upsert_user(username, role="technician")
    record = repo.get_user_by_username(username)
    assert record is not None
    return record.user_id


def test_active_device_ids_for_user_returns_assigned_devices():
    # Child table (assignments) before parent (users): a prior test in this
    # module-scoped schema may have left assignment rows FK-referencing its
    # users, which would block clear_all_users() if deleted in the other order.
    repo.delete_all_assignments()
    clear_all_users()
    _seed_tree("sc-p1", "sc-p1-t1", ["sc-d1", "sc-d2", "sc-d3"])
    user_id = _technician("scope-tech")

    repo.assign_device_to_user("sc-d1", "scope-tech", None)
    repo.assign_device_to_user("sc-d3", "scope-tech", None)

    assert sorted(repo.list_active_device_ids_for_user(user_id)) == ["sc-d1", "sc-d3"]


def test_active_device_ids_for_user_excludes_ended_assignments():
    """Invariant 2: current active assignments, never history."""
    repo.delete_all_assignments()
    clear_all_users()
    _seed_tree("sc-p2", "sc-p2-t1", ["sc-e1"])
    user_id = _technician("ended-tech")

    repo.assign_device_to_user("sc-e1", "ended-tech", None)
    repo.end_active_device_assignment("sc-e1")

    assert repo.list_active_device_ids_for_user(user_id) == []


def test_active_device_ids_for_unknown_user_is_empty():
    assert repo.list_active_device_ids_for_user(-1) == []


def test_scope_clause_unrestricted_is_empty_sql():
    sql, params = repo._scope_clause("d", None)
    assert sql == ""
    assert params == {}


def test_scope_clause_constrained_binds_the_set():
    sql, params = repo._scope_clause("d", frozenset({"a", "b"}))
    assert "d.device_id IN" in sql
    assert sorted(params["allowed_device_ids"]) == ["a", "b"]


def test_scope_clause_empty_set_is_still_a_constraint():
    """Invariant 8: EMPTY must never degrade to unrestricted."""
    sql, params = repo._scope_clause("d", frozenset())
    assert "d.device_id IN" in sql
    assert params["allowed_device_ids"] == []
