"""ADMIN-2S — the opt-in administration demo seed.

Two concerns. The pure half is determinism: repeated resets must reproduce the
same technician/device relationships, or a demo stops being reproducible and
screenshots stop matching the database. The database half is containment: this
seed writes people and assignments, and it must never touch a user it did not
create.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from db.engine import session_scope
from db.generators import registration_timestamp
from db.hierarchy import build_hierarchy
from db.seed_admin_demo import (
    ASSIGNED_DEVICE_COUNT,
    DEMO_TECHNICIANS,
    TECHNICIAN_LOAD,
    DemoSeedRefused,
    assignment_plan,
    demo_usernames,
    reset_demo_data,
    seed_admin_demo,
)
from repositories import plant_monitoring_repository as repo

ANCHOR = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
PLANT_IDS = [f"plant-{i:02d}" for i in range(1, 31)]


def all_device_ids() -> list[str]:
    _transformers, devices = build_hierarchy(
        PLANT_IDS, {p: "Country" for p in PLANT_IDS}
    )
    return [d.device_id for d in devices]


# ---------------------------------------------------------------------------
# Pure planning — no database
# ---------------------------------------------------------------------------

class TestDemoTechnicianIdentities:
    def test_there_are_five(self):
        assert len(DEMO_TECHNICIANS) == 5

    def test_every_identity_is_a_technician(self):
        assert all(t.role == "technician" for t in DEMO_TECHNICIANS)

    def test_every_identity_is_active(self):
        assert all(t.status == "active" for t in DEMO_TECHNICIANS)

    def test_usernames_are_unique(self):
        assert len(set(demo_usernames())) == len(DEMO_TECHNICIANS)

    def test_identities_are_obviously_synthetic(self):
        """No client person's name is copied into development data, and the
        addresses use a reserved TLD that can never route."""
        for t in DEMO_TECHNICIANS:
            assert t.username.startswith("demo.")
            assert t.email_address.endswith(".invalid")
            assert "Demo" in t.full_name


class TestAssignmentPlan:
    def test_assigns_the_documented_number_of_devices(self):
        assert len(assignment_plan(all_device_ids())) == ASSIGNED_DEVICE_COUNT

    def test_leaves_the_rest_unassigned(self):
        devices = all_device_ids()
        planned = {d for d, _u in assignment_plan(devices)}
        assert len(set(devices) - planned) == 120 - ASSIGNED_DEVICE_COUNT

    def test_is_deterministic(self):
        assert assignment_plan(all_device_ids()) == assignment_plan(all_device_ids())

    def test_is_independent_of_input_ordering(self):
        """A reseed must not depend on the order the hierarchy happened to
        enumerate devices in."""
        forward = assignment_plan(all_device_ids())
        backward = assignment_plan(list(reversed(all_device_ids())))
        assert dict(forward) == dict(backward)

    def test_plans_only_devices_it_was_given(self):
        devices = set(all_device_ids())
        assert all(d in devices for d, _u in assignment_plan(all_device_ids()))

    def test_assigns_each_device_at_most_once(self):
        planned = [d for d, _u in assignment_plan(all_device_ids())]
        assert len(planned) == len(set(planned))

    def test_uses_every_technician(self):
        used = {u for _d, u in assignment_plan(all_device_ids())}
        assert used == set(demo_usernames())

    def test_loads_match_the_documented_split(self):
        loads = dict.fromkeys(demo_usernames(), 0)
        for _d, username in assignment_plan(all_device_ids()):
            loads[username] += 1
        assert [loads[u] for u in demo_usernames()] == list(TECHNICIAN_LOAD)

    def test_loads_are_uneven(self):
        """An operational system does not distribute work perfectly evenly.
        Cosmetic realism only — no workload model is implied."""
        assert len(set(TECHNICIAN_LOAD)) > 1

    def test_documented_split_sums_to_the_assigned_count(self):
        assert sum(TECHNICIAN_LOAD) == ASSIGNED_DEVICE_COUNT

    def test_handles_fewer_devices_than_the_planned_total(self):
        """A partially seeded database must not raise or over-assign."""
        plan = assignment_plan(all_device_ids()[:10])
        assert len(plan) == 10
        assert len({d for d, _u in plan}) == 10

    def test_handles_no_devices(self):
        assert assignment_plan([]) == ()


class TestUnassignedSelectionIsNotAnArtifact:
    """The unassigned RTLs must not secretly be "the oldest ones".

    Registration dates and assignment selection are both hashes of device_id.
    Derived from the *same* hash they would correlate perfectly, and ADMIN-3's
    exception table would show a pattern nobody designed.
    """

    def _unassigned(self) -> set[str]:
        devices = all_device_ids()
        planned = {d for d, _u in assignment_plan(devices)}
        return set(devices) - planned

    def test_unassigned_are_not_the_oldest_devices(self):
        devices = all_device_ids()
        oldest = set(
            sorted(devices, key=lambda d: registration_timestamp(d, ANCHOR))[
                : 120 - ASSIGNED_DEVICE_COUNT
            ]
        )
        assert self._unassigned() != oldest

    def test_unassigned_span_multiple_plants(self):
        plants = {d.split("-t")[0] for d in self._unassigned()}
        assert len(plants) > 1


# ---------------------------------------------------------------------------
# Database behaviour — isolated schema, never the real one
# ---------------------------------------------------------------------------

def _seed_devices(device_ids: list[str]) -> None:
    """Minimal hierarchy so device_id satisfies the assignments FK."""
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants "
                f"(plant_id, name, country, latitude, longitude) "
                f"VALUES ('demo-p1', 'Demo Plant', 'Testland', 0, 0) "
                f"ON CONFLICT (plant_id) DO NOTHING"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES ('demo-p1-t1', 'demo-p1', 't1') "
                f"ON CONFLICT (transformer_id) DO NOTHING"
            )
        )
        for index, device_id in enumerate(device_ids):
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.devices "
                    f"(device_id, transformer_id, device_code) "
                    f"VALUES (:device_id, 'demo-p1-t1', :device_code) "
                    f"ON CONFLICT (device_id) DO NOTHING"
                ),
                # devices.device_code is varchar(10); device_id does not fit.
                {"device_id": device_id, "device_code": str(29001 + index)},
            )


def _active_assignments() -> dict[str, str]:
    """{device_id: technician_username} for every open assignment."""
    with session_scope() as session:
        rows = session.execute(
            text(
                f"SELECT a.device_id, u.username "
                f"FROM {repo._SCHEMA}.user_device_assignments a "
                f"JOIN {repo._SCHEMA}.users u ON u.user_id = a.user_id "
                f"WHERE a.ended_at IS NULL"
            )
        ).all()
    return {device_id: username for device_id, username in rows}


def _usernames() -> set[str]:
    return {u.username for u in repo.list_users()}


class TestSeedingAgainstTheDatabase:
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    @pytest.fixture(autouse=True)
    def _clean_slate(self):
        """`isolated_schema` is module-scoped and shared by every test in this
        file, so users and assignments must be cleared per test. Devices are
        left in place — they are inert here and re-inserting 120 rows per test
        buys nothing.
        """
        repo.delete_all_assignments()
        repo.delete_all_users()
        yield

    def test_creates_the_demo_technicians(self):
        _seed_devices(all_device_ids())
        seed_admin_demo()
        assert set(demo_usernames()) <= _usernames()

    def test_assigns_the_documented_number_of_devices(self):
        _seed_devices(all_device_ids())
        summary = seed_admin_demo()
        assert summary.assigned_devices == ASSIGNED_DEVICE_COUNT
        assert len(_active_assignments()) == ASSIGNED_DEVICE_COUNT

    def test_reported_summary_matches_the_database(self):
        _seed_devices(all_device_ids())
        summary = seed_admin_demo()
        assert summary.total_devices == 120
        assert summary.unassigned_devices == 120 - ASSIGNED_DEVICE_COUNT
        assert summary.active_technicians == len(DEMO_TECHNICIANS)

    def test_is_idempotent(self):
        """Re-running without --reset must not duplicate users or assignments."""
        _seed_devices(all_device_ids())
        seed_admin_demo()
        first = _active_assignments()
        seed_admin_demo()
        assert _active_assignments() == first
        assert len(_usernames()) == len(DEMO_TECHNICIANS)

    def test_idempotent_run_adds_no_history_rows(self):
        """assign_device_to_user() leaves an unchanged assignment alone rather
        than closing and reopening it, so a second run writes no history."""
        _seed_devices(all_device_ids())
        seed_admin_demo()

        def total_rows() -> int:
            with session_scope() as session:
                return session.execute(
                    text(
                        f"SELECT COUNT(*) FROM "
                        f"{repo._SCHEMA}.user_device_assignments"
                    )
                ).scalar_one()

        before = total_rows()
        seed_admin_demo()
        assert total_rows() == before

    def test_repeated_reset_reproduces_the_same_relationships(self):
        _seed_devices(all_device_ids())
        seed_admin_demo()
        first = _active_assignments()
        reset_demo_data()
        seed_admin_demo()
        assert _active_assignments() == first

    def test_one_active_assignment_per_device(self):
        _seed_devices(all_device_ids())
        seed_admin_demo()
        seed_admin_demo()
        with session_scope() as session:
            worst = session.execute(
                text(
                    f"SELECT COUNT(*) FROM {repo._SCHEMA}.user_device_assignments "
                    f"WHERE ended_at IS NULL "
                    f"GROUP BY device_id ORDER BY COUNT(*) DESC LIMIT 1"
                )
            ).scalar_one()
        assert worst == 1


class TestItOnlyTouchesWhatItCreated:
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    @pytest.fixture(autouse=True)
    def _clean_slate(self):
        """`isolated_schema` is module-scoped and shared by every test in this
        file, so users and assignments must be cleared per test. Devices are
        left in place — they are inert here and re-inserting 120 rows per test
        buys nothing.
        """
        repo.delete_all_assignments()
        repo.delete_all_users()
        yield

    def test_reset_leaves_non_demo_users_alone(self):
        _seed_devices(all_device_ids())
        repo.create_or_update_user(
            username="admin", full_name="admin", role="general", status="active"
        )
        seed_admin_demo()
        reset_demo_data()
        assert "admin" in _usernames()
        assert not set(demo_usernames()) & _usernames()

    def test_reset_removes_only_demo_assignments(self):
        _seed_devices(all_device_ids())
        repo.create_or_update_user(
            username="real.tech",
            full_name="Real Technician",
            role="technician",
            status="active",
        )
        kept = all_device_ids()[0]
        repo.assign_device_to_user(device_id=kept, technician_username="real.tech")
        seed_admin_demo()
        reset_demo_data()
        assert _active_assignments() == {kept: "real.tech"}

    def test_seeding_does_not_steal_a_device_a_real_technician_holds(self):
        """A device already assigned outside this seed keeps its technician."""
        _seed_devices(all_device_ids())
        repo.create_or_update_user(
            username="real.tech",
            full_name="Real Technician",
            role="technician",
            status="active",
        )
        held = all_device_ids()[0]
        repo.assign_device_to_user(device_id=held, technician_username="real.tech")
        seed_admin_demo()
        assert _active_assignments()[held] == "real.tech"

    def test_refuses_to_overwrite_a_stranger_holding_a_demo_username(self):
        """A demo username is claimed only if the existing row is recognisably
        the identity this seed created."""
        _seed_devices(all_device_ids())
        repo.create_or_update_user(
            username=DEMO_TECHNICIANS[0].username,
            full_name="A Real Person",
            role="administrator",
            status="active",
            email_address="real.person@example.com",
        )
        with pytest.raises(DemoSeedRefused):
            seed_admin_demo()

    def test_a_refused_seed_assigns_nothing(self):
        _seed_devices(all_device_ids())
        repo.create_or_update_user(
            username=DEMO_TECHNICIANS[0].username,
            full_name="A Real Person",
            role="administrator",
            status="active",
            email_address="real.person@example.com",
        )
        with pytest.raises(DemoSeedRefused):
            seed_admin_demo()
        assert _active_assignments() == {}

    def test_reset_is_safe_to_run_when_nothing_was_seeded(self):
        reset_demo_data()
        assert _active_assignments() == {}
