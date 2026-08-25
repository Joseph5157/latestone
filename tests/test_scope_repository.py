"""Repository-level scope constraint tests.

Runs against a disposable schema â€” never the developer's real
plant_monitoring.* tables. See tests/conftest.py::isolated_schema.
"""
from __future__ import annotations

from datetime import datetime, timezone

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


def _auditor_id() -> int:
    """AUD-1: audited service writes require an authenticated actor; this
    one is created at repository level (no audit row)."""
    return repo.create_or_update_user(
        username="scope-auditor",
        full_name="scope-auditor",
        role="administrator",
        status="active",
    ).user_id


def _technician(username: str) -> int:
    upsert_user(username, role="technician", actor_user_id=_auditor_id())
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
    """Spec Â§4.3: scope and include_inactive are independent and both apply.

    An assigned-but-inactive device stays hidden under the active-only
    default â€” assignment membership must not resurrect it.
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


def test_hierarchy_counts_transformer_count_agrees_with_list_transformers():
    """A plant with a mix of visible and invisible transformers must report
    the transformer count list_transformers would actually list, not every
    transformer that happens to hold a status-eligible row."""
    _seed_tree("sc-p13", "sc-p13-t1", ["sc-p13-d1"])
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES ('sc-p13-t2', 'sc-p13', 't2') ON CONFLICT DO NOTHING"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.devices "
                f"(device_id, transformer_id, device_code) "
                f"VALUES ('sc-p13-d2', 'sc-p13-t2', 'd2') ON CONFLICT DO NOTHING"
            )
        )

    scope = frozenset({"sc-p13-d1"})

    counts = repo.count_hierarchy_by_plant(allowed_device_ids=scope)
    listed_transformers = repo.list_transformers("sc-p13", allowed_device_ids=scope)

    assert counts["sc-p13"] == (1, 1)
    assert counts["sc-p13"][0] == len(listed_transformers), (
        "the transformer count must agree with what list_transformers actually lists"
    )


def test_latest_reading_times_constrained_to_visible_devices():
    _seed_tree("sc-p13b", "sc-p13b-t1", ["sc-r1", "sc-r2"])

    rows = repo.latest_reading_times(
        ["temperature"], allowed_device_ids=frozenset({"sc-r1"})
    )

    assert {r.device_id for r in rows} == {"sc-r1"}


def test_latest_reading_times_empty_scope_returns_nothing():
    """Invariant 8 on the query that feeds every freshness figure."""
    _seed_tree("sc-p14", "sc-p14-t1", ["sc-r9"])
    assert repo.latest_reading_times(
        ["temperature"], allowed_device_ids=frozenset()
    ) == []


def test_latest_metric_readings_constrained_to_visible_devices():
    _seed_tree("sc-p15", "sc-p15-t1", ["sc-m1", "sc-m2"])

    rows = repo.latest_metric_readings(
        "temperature",
        transformer_id="sc-p15-t1",
        allowed_device_ids=frozenset({"sc-m2"}),
    )

    assert {r.device_id for r in rows} == {"sc-m2"}


def test_latest_metric_readings_empty_scope_returns_nothing():
    _seed_tree("sc-p16", "sc-p16-t1", ["sc-m9"])
    assert repo.latest_metric_readings(
        "temperature",
        transformer_id="sc-p16-t1",
        allowed_device_ids=frozenset(),
    ) == []


def test_notification_rows_are_empty_for_an_empty_scope():
    """Spec Â§7.1(1): notifications derive from latest_reading_times rather
    than a query of their own, which makes them the easiest surface to leave
    unscoped by accident."""
    from services.device_scope import EMPTY
    from services import monitoring_service
    from services.notification_service import build_current_notifications

    _seed_tree("sc-p14b", "sc-p14b-t1", ["sc-r10"])
    rows = monitoring_service.latest_reading_rows(scope=EMPTY)

    assert rows == []
    assert build_current_notifications(rows, datetime.now(timezone.utc)) == []


def test_reading_population_agrees_with_hierarchy_counts_under_scope():
    """Two figures rendered on the same screen must describe the same population.

    latest_reading_times is device-grained and rolled up in Python;
    count_hierarchy_by_plant aggregates in SQL. They must still agree about how
    many transformers a scoped user can see, or the Fleet card and the freshness
    column contradict each other.
    """
    _seed_tree("agree-p1", "agree-p1-t1", ["agree-d1"])
    # second transformer under the SAME plant, holding an out-of-scope device
    # (mirrors test_hierarchy_counts_transformer_count_agrees_with_list_transformers)
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES ('agree-p1-t2', 'agree-p1', 't2') ON CONFLICT DO NOTHING"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.devices "
                f"(device_id, transformer_id, device_code) "
                f"VALUES ('agree-d2', 'agree-p1-t2', 'd2') ON CONFLICT DO NOTHING"
            )
        )

    scope = frozenset({"agree-d1"})

    rows = repo.latest_reading_times(["temperature"], allowed_device_ids=scope)
    tx_from_rows = {r.transformer_id for r in rows}
    tx_from_counts, _devices = repo.count_hierarchy_by_plant(
        allowed_device_ids=scope
    )["agree-p1"]

    assert len(tx_from_rows) == tx_from_counts == 1


# ==========================================================================
# ROLE-3 Task 13 â€” end-to-end scope behaviour
#
# The tests above pin individual queries. These assert the whole thing
# through the service layer, which is where filtering-after-aggregation
# would show through: a query can be right and the number on the card still
# wrong, because the card is built from a different call.
# ==========================================================================


def test_technician_sees_only_their_slice_of_the_hierarchy():
    """The whole point, asserted through the service layer."""
    from services import hierarchy_service
    from services.device_scope import DeviceScope

    # Child table before parent: user_device_assignments.user_id has an FK
    # to users.user_id, and isolated_schema is module-scoped, so rows from
    # an earlier test in this file are still present.
    repo.delete_all_assignments()
    clear_all_users()
    _seed_tree("e2e-p1", "e2e-p1-t1", ["e2e-d1", "e2e-d2"])
    _seed_tree("e2e-p2", "e2e-p2-t1", ["e2e-d3"])
    user_id = _technician("e2e-tech")
    repo.assign_device_to_user("e2e-d1", "e2e-tech", None)

    scope = DeviceScope(frozenset(repo.list_active_device_ids_for_user(user_id)))

    plant_ids = [p.plant_id for p in hierarchy_service.list_plants(scope=scope)]
    assert "e2e-p1" in plant_ids
    assert "e2e-p2" not in plant_ids

    devices = hierarchy_service.list_devices("e2e-p1-t1", scope=scope)
    assert [d.device_id for d in devices] == ["e2e-d1"]

    counts = hierarchy_service.get_plant_hierarchy_counts(scope=scope)
    assert counts["e2e-p1"] == (1, 1), "Invariant 4: counted over the visible set"


def test_technician_with_no_assignments_sees_an_empty_fleet():
    from services import hierarchy_service
    from services.device_scope import EMPTY

    assert hierarchy_service.list_plants(scope=EMPTY) == []
    assert hierarchy_service.get_plant_hierarchy_counts(scope=EMPTY) == {}


def test_fleet_kpi_cards_report_the_visible_population():
    """Spec 7.1(3): asserted on the rendered KPI numbers, not just the query
    result. This is where filtering-after-aggregation would show through â€” the
    query could be right and the card still wrong."""
    from components.fleet_summary import fleet_kpi_cards
    from services import hierarchy_service, monitoring_service
    from services.device_scope import DeviceScope
    from tests.dash_tree import text_of

    # Child table before parent: user_device_assignments.user_id has an FK
    # to users.user_id, and isolated_schema is module-scoped, so rows from
    # an earlier test in this file are still present.
    repo.delete_all_assignments()
    clear_all_users()
    _seed_tree("kpi-p1", "kpi-p1-t1", ["kpi-d1", "kpi-d2"])
    _seed_tree("kpi-p2", "kpi-p2-t1", ["kpi-d3"])
    scope = DeviceScope(frozenset({"kpi-d1"}))

    now = datetime.now(timezone.utc)
    plants = hierarchy_service.list_plants(scope=scope)
    counts = hierarchy_service.get_plant_hierarchy_counts(scope=scope)
    health = monitoring_service.get_fleet_health(now, scope=scope)

    visible_devices = sum(d for _t, d in counts.values())
    assert len(plants) == 1, "only the plant holding kpi-d1 is visible"
    assert visible_devices == 1, "Invariant 4: counted over the visible set"

    cards = fleet_kpi_cards(
        plants=len(plants),
        transformers=sum(t for t, _d in counts.values()),
        devices=visible_devices,
        health=health,
    )

    # Assert on the health rollup the card renders rather than searching the
    # card's text for a bare digit â€” "3" appears in unrelated copy, and a
    # negative substring assertion would pass or fail for the wrong reasons.
    assert sum(health.counts.values()) == 1, (
        "the Data Health card must describe one device, not three"
    )
    assert text_of(cards), "cards rendered"


def test_unrestricted_scope_is_unchanged_from_pre_role_3_behaviour():
    """Invariant: an administrator's experience must not change."""
    from services import hierarchy_service
    from services.device_scope import UNRESTRICTED

    _seed_tree("reg-p1", "reg-p1-t1", ["reg-d1", "reg-d2"])
    devices = hierarchy_service.list_devices("reg-p1-t1", scope=UNRESTRICTED)
    assert sorted(d.device_id for d in devices) == ["reg-d1", "reg-d2"]


def test_general_sees_the_same_population_as_the_administrator():
    """Invariant 3, end to end: read-only is a constraint on ACTIONS.

    Both roles resolve to UNRESTRICTED, so this asserts they are literally
    the same object rather than two independently-maintained answers that
    could drift.
    """
    from services import hierarchy_service
    from services.auth_service import AuthenticatedUser
    from services.device_scope import UNRESTRICTED, scope_for

    repo.delete_all_assignments()
    clear_all_users()
    _seed_tree("both-p1", "both-p1-t1", ["both-d1", "both-d2"])

    def _user(role):
        return AuthenticatedUser(user_id=1, username="u", full_name="U", role=role)

    admin_scope = scope_for(_user("administrator"))
    general_scope = scope_for(_user("general"))

    assert admin_scope == general_scope == UNRESTRICTED

    admin_devices = hierarchy_service.list_devices("both-p1-t1", scope=admin_scope)
    general_devices = hierarchy_service.list_devices("both-p1-t1", scope=general_scope)
    assert [d.device_id for d in admin_devices] == [
        d.device_id for d in general_devices
    ]
    assert len(general_devices) == 2


def test_ending_the_last_assignment_empties_the_hierarchy():
    """History grants nothing, asserted at the VISIBILITY layer.

    tests/test_action_guard_db.py pins this for actions. This is the other
    half: once the assignment ends, the technician's fleet is empty too.
    """
    from services import hierarchy_service
    from services.device_scope import DeviceScope

    repo.delete_all_assignments()
    clear_all_users()
    _seed_tree("hist-p1", "hist-p1-t1", ["hist-d1"])
    user_id = _technician("hist-tech")
    repo.assign_device_to_user("hist-d1", "hist-tech", None)

    scope = DeviceScope(frozenset(repo.list_active_device_ids_for_user(user_id)))
    assert len(hierarchy_service.list_plants(scope=scope)) == 1

    repo.end_active_device_assignment("hist-d1")

    after = DeviceScope(frozenset(repo.list_active_device_ids_for_user(user_id)))
    assert after.device_ids == frozenset()
    assert after.is_unrestricted is False, "EMPTY must never become unrestricted"
    assert hierarchy_service.list_plants(scope=after) == []
    assert hierarchy_service.get_plant_hierarchy_counts(scope=after) == {}
