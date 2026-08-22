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


def test_list_devices_unrestricted_returns_every_device():
    _seed_tree("sc-p3", "sc-p3-t1", ["sc-u1", "sc-u2"])
    rows = repo.list_devices("sc-p3-t1", allowed_device_ids=None)
    assert sorted(r.device_id for r in rows) == ["sc-u1", "sc-u2"]


def test_list_devices_constrained_returns_only_scoped_devices():
    _seed_tree("sc-p4", "sc-p4-t1", ["sc-a1", "sc-a2", "sc-a3"])
    rows = repo.list_devices(
        "sc-p4-t1", allowed_device_ids=frozenset({"sc-a1", "sc-a3"})
    )
    assert sorted(r.device_id for r in rows) == ["sc-a1", "sc-a3"]


def test_list_devices_empty_scope_returns_nothing():
    """Invariant 8, proven against real SQL: the empty expanding bindparam
    must match nothing, not everything."""
    _seed_tree("sc-p5", "sc-p5-t1", ["sc-z1", "sc-z2"])
    rows = repo.list_devices("sc-p5-t1", allowed_device_ids=frozenset())
    assert rows == []


def test_list_devices_requires_the_scope_keyword():
    """Invariant 8: an omitted argument must never mean 'show everything'."""
    with pytest.raises(TypeError):
        repo.list_devices("sc-p5-t1")


def test_scope_narrows_but_never_widens_past_the_status_filter():
    """Spec §4.3: scope and include_inactive are independent and both apply.

    An assigned-but-inactive device stays hidden under the active-only
    default — assignment membership must not resurrect it.
    """
    from services import hierarchy_service
    from services.device_scope import DeviceScope

    _seed_tree("sc-p5b", "sc-p5b-t1", ["sc-inact"])
    with session_scope() as session:
        session.execute(
            text(
                f"UPDATE {repo._SCHEMA}.devices SET status = 'inactive' "
                f"WHERE device_id = 'sc-inact'"
            )
        )

    scope = DeviceScope(frozenset({"sc-inact"}))

    assert hierarchy_service.list_devices("sc-p5b-t1", scope=scope) == []
    assert [
        d.device_id
        for d in hierarchy_service.list_devices(
            "sc-p5b-t1", scope=scope, include_inactive=True
        )
    ] == ["sc-inact"]


def test_list_plants_constrained_to_plants_holding_a_visible_device():
    _seed_tree("sc-p6", "sc-p6-t1", ["sc-p6-d1"])
    _seed_tree("sc-p7", "sc-p7-t1", ["sc-p7-d1"])

    rows = repo.list_plants(allowed_device_ids=frozenset({"sc-p6-d1"}))
    plant_ids = [r.plant_id for r in rows]

    assert "sc-p6" in plant_ids
    assert "sc-p7" not in plant_ids


def test_list_plants_empty_scope_returns_nothing():
    _seed_tree("sc-p8", "sc-p8-t1", ["sc-p8-d1"])
    assert repo.list_plants(allowed_device_ids=frozenset()) == []


def test_list_transformers_constrained_to_those_holding_a_visible_device():
    _seed_tree("sc-p9", "sc-p9-t1", ["sc-p9-d1"])
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES ('sc-p9-t2', 'sc-p9', 't2') ON CONFLICT DO NOTHING"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.devices "
                f"(device_id, transformer_id, device_code) "
                f"VALUES ('sc-p9-d2', 'sc-p9-t2', 'd2') ON CONFLICT DO NOTHING"
            )
        )

    rows = repo.list_transformers("sc-p9", allowed_device_ids=frozenset({"sc-p9-d1"}))

    assert [r.transformer_id for r in rows] == ["sc-p9-t1"]


def test_list_transformers_empty_scope_returns_nothing():
    _seed_tree("sc-p10", "sc-p10-t1", ["sc-p10-d1"])
    assert repo.list_transformers("sc-p10", allowed_device_ids=frozenset()) == []


def test_hierarchy_counts_are_computed_over_the_visible_population():
    """Invariant 4: filtered before aggregation, not trimmed after."""
    _seed_tree("sc-p11", "sc-p11-t1", ["sc-c1", "sc-c2", "sc-c3"])

    counts = repo.count_hierarchy_by_plant(
        allowed_device_ids=frozenset({"sc-c1"})
    )

    transformers, devices = counts["sc-p11"]
    assert devices == 1, "count must reflect the visible device, not all three"
    assert transformers == 1


def test_hierarchy_counts_empty_scope_yields_no_plants():
    _seed_tree("sc-p12", "sc-p12-t1", ["sc-c9"])
    assert repo.count_hierarchy_by_plant(allowed_device_ids=frozenset()) == {}
