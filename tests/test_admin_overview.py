"""Tests for the ADMIN-1 administration summary data layer.

Two layers, tested separately:

- Repository (database-backed, `db`-marked): the new aggregate/anti-join
  queries, run against the disposable `isolated_schema` (tests/conftest.py)
  so they never touch the developer's real plant_monitoring rows.
- Service (pure where practical): the 7-day registration window and the
  composition of repository results into `AdminOverviewSummary`.

The clock is always injected, never read: every time-sensitive assertion
pins `now` to the module-level `NOW`, matching the convention in
tests/test_monitoring_service.py.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import admin_overview_service as admin_overview


#: One fixed instant for every time-sensitive assertion. Nothing in these
#: tests may consult the real clock.
NOW = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixture helpers — raw inserts so a test controls exactly what exists.
# ---------------------------------------------------------------------------

def _reset_hierarchy() -> None:
    """Empty the tables these tests own, in FK-safe order."""
    with session_scope() as session:
        session.execute(text(f"DELETE FROM {repo._SCHEMA}.user_device_assignments"))
        session.execute(text(f"DELETE FROM {repo._SCHEMA}.devices"))
        session.execute(text(f"DELETE FROM {repo._SCHEMA}.transformers"))
        session.execute(text(f"DELETE FROM {repo._SCHEMA}.plants"))
        session.execute(text(f"DELETE FROM {repo._SCHEMA}.users"))


def _database_now() -> datetime:
    """The database's clock, not the host's.

    `devices.created_at` is defaulted by PostgreSQL, so a window built from
    `datetime.now()` on the host compares two different clock domains. They
    are not the same clock: the container has been measured running several
    milliseconds ahead of the host, which is enough for a row to land outside
    the closed interval that was supposed to contain it. Any assertion about
    a database-generated timestamp takes its bounds from here.
    """
    with session_scope() as session:
        return session.execute(text("SELECT now()")).scalar()


def _seed_plant(plant_id: str, name: str) -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants "
                f"(plant_id, name, country, latitude, longitude) "
                f"VALUES (:plant_id, :name, 'Testland', 0, 0) "
                f"ON CONFLICT (plant_id) DO NOTHING"
            ),
            {"plant_id": plant_id, "name": name},
        )


def _seed_transformer(transformer_id: str, plant_id: str, code: str) -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES (:transformer_id, :plant_id, :code) "
                f"ON CONFLICT (transformer_id) DO NOTHING"
            ),
            {"transformer_id": transformer_id, "plant_id": plant_id, "code": code},
        )


def _seed_device(
    device_id: str,
    transformer_id: str,
    device_code: str,
    status: str = "active",
    created_at: datetime | None = None,
) -> None:
    """Insert one device. `created_at` is written explicitly when supplied so
    the recently-registered window can be tested without waiting or sleeping.
    """
    with session_scope() as session:
        if created_at is None:
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.devices "
                    f"(device_id, transformer_id, device_code, status) "
                    f"VALUES (:device_id, :transformer_id, :device_code, :status)"
                ),
                {
                    "device_id": device_id,
                    "transformer_id": transformer_id,
                    "device_code": device_code,
                    "status": status,
                },
            )
        else:
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.devices "
                    f"(device_id, transformer_id, device_code, status, created_at) "
                    f"VALUES (:device_id, :transformer_id, :device_code, :status, :created_at)"
                ),
                {
                    "device_id": device_id,
                    "transformer_id": transformer_id,
                    "device_code": device_code,
                    "status": status,
                    "created_at": created_at,
                },
            )


def _seed_user(username: str, role: str, status: str = "active") -> None:
    repo.create_or_update_user(
        username=username, full_name=username, role=role, status=status
    )


def _set_transformer_status(transformer_id: str, status: str) -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"UPDATE {repo._SCHEMA}.transformers SET status = :status "
                f"WHERE transformer_id = :transformer_id"
            ),
            {"transformer_id": transformer_id, "status": status},
        )


#: Every standard-hierarchy device is dated well outside any window under
#: test. Leaving `created_at` to the database default would make the
#: recently-registered assertions depend on what time of day the suite runs:
#: on a day equal to NOW's date, a defaulted row can land inside or outside
#: [NOW - 7d, NOW] depending on the wall clock.
LONG_AGO = NOW - timedelta(days=365)


def _seed_standard_hierarchy() -> None:
    """Two plants, three transformers, four active devices.

    Names/codes are chosen so alphabetical plant-name ordering ("Alpha"
    before "Bravo") differs from insertion order, which is what makes the
    ordering assertions meaningful.
    """
    _seed_plant("p-bravo", "Bravo Plant")
    _seed_plant("p-alpha", "Alpha Plant")
    _seed_transformer("p-bravo-t1", "p-bravo", "bv01")
    _seed_transformer("p-alpha-t1", "p-alpha", "al01")
    _seed_transformer("p-alpha-t2", "p-alpha", "al02")
    _seed_device("p-bravo-t1-d1", "p-bravo-t1", "40001", created_at=LONG_AGO)
    _seed_device("p-alpha-t1-d1", "p-alpha-t1", "40002", created_at=LONG_AGO)
    _seed_device("p-alpha-t1-d2", "p-alpha-t1", "40003", created_at=LONG_AGO)
    _seed_device("p-alpha-t2-d1", "p-alpha-t2", "40004", created_at=LONG_AGO)


# ---------------------------------------------------------------------------
# Repository — assignment counts
# ---------------------------------------------------------------------------

class TestCountDeviceAssignments:
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    def setup_method(self):
        _reset_hierarchy()
        _seed_standard_hierarchy()

    def test_no_assignments_reports_every_device_unassigned(self):
        counts = repo.count_device_assignments()

        assert counts.total_devices == 4
        assert counts.assigned_devices == 0
        assert counts.unassigned_devices == 4

    def test_one_active_assignment_is_counted(self):
        _seed_user("tech-a", "technician")
        repo.assign_device_to_user("p-alpha-t1-d1", "tech-a")

        counts = repo.count_device_assignments()

        assert counts.assigned_devices == 1
        assert counts.unassigned_devices == 3

    def test_several_devices_assigned_to_one_technician_each_count(self):
        _seed_user("tech-a", "technician")
        repo.assign_device_to_user("p-alpha-t1-d1", "tech-a")
        repo.assign_device_to_user("p-alpha-t1-d2", "tech-a")
        repo.assign_device_to_user("p-bravo-t1-d1", "tech-a")

        counts = repo.count_device_assignments()

        assert counts.assigned_devices == 3
        assert counts.unassigned_devices == 1

    def test_ended_assignment_is_not_active(self):
        _seed_user("tech-a", "technician")
        repo.assign_device_to_user("p-alpha-t1-d1", "tech-a")
        repo.end_active_device_assignment("p-alpha-t1-d1")

        counts = repo.count_device_assignments()

        assert counts.assigned_devices == 0
        assert counts.unassigned_devices == 4

    def test_reassignment_still_counts_one_assigned_device(self):
        _seed_user("tech-a", "technician")
        _seed_user("tech-b", "technician")
        repo.assign_device_to_user("p-alpha-t1-d1", "tech-a")
        repo.assign_device_to_user("p-alpha-t1-d1", "tech-b")

        # Two history rows now exist for this device; only one is active.
        assert len(repo.list_assignment_history("p-alpha-t1-d1")) == 2

        counts = repo.count_device_assignments()

        assert counts.assigned_devices == 1
        assert counts.unassigned_devices == 3

    def test_device_with_assignment_history_is_not_double_counted(self):
        _seed_user("tech-a", "technician")
        _seed_user("tech-b", "technician")
        # Three closed rows plus one active row, all for the same device.
        repo.assign_device_to_user("p-alpha-t1-d1", "tech-a")
        repo.assign_device_to_user("p-alpha-t1-d1", "tech-b")
        repo.assign_device_to_user("p-alpha-t1-d1", "tech-a")
        repo.assign_device_to_user("p-alpha-t1-d1", "tech-b")

        counts = repo.count_device_assignments()

        assert counts.total_devices == 4
        assert counts.assigned_devices == 1

    def test_total_always_splits_into_assigned_and_unassigned(self):
        _seed_user("tech-a", "technician")
        repo.assign_device_to_user("p-alpha-t1-d1", "tech-a")
        repo.assign_device_to_user("p-bravo-t1-d1", "tech-a")

        counts = repo.count_device_assignments()

        assert counts.assigned_devices + counts.unassigned_devices == counts.total_devices

    def test_no_devices_reports_zero_everywhere(self):
        _reset_hierarchy()

        counts = repo.count_device_assignments()

        assert counts.total_devices == 0
        assert counts.assigned_devices == 0
        assert counts.unassigned_devices == 0

    def test_inactive_devices_are_excluded_by_default(self):
        _seed_device("p-alpha-t2-d2", "p-alpha-t2", "40005", status="inactive")

        counts = repo.count_device_assignments()

        assert counts.total_devices == 4

    def test_inactive_devices_are_included_on_request(self):
        _seed_device("p-alpha-t2-d2", "p-alpha-t2", "40005", status="inactive")

        counts = repo.count_device_assignments(include_inactive=True)

        assert counts.total_devices == 5

    def test_population_matches_the_device_management_table(self):
        # The admin summary must describe exactly the device population the
        # Device Management page lists, or the two screens disagree.
        _seed_device("p-alpha-t2-d2", "p-alpha-t2", "40005", status="inactive")

        counts = repo.count_device_assignments()

        assert counts.total_devices == len(repo.list_all_devices())


# ---------------------------------------------------------------------------
# Repository — the two device populations
#
# Monitoring Devices = active devices under active transformers.
# Managed RTLs       = administratively active devices, regardless of
#                      transformer status.
#
# On the current development data these are the same 120 devices, because
# nothing is deactivated — which is exactly why the difference needs pinning
# rather than leaving to be discovered later. One active device under an
# INACTIVE transformer is the whole separation, so every test here turns on
# that single row.
# ---------------------------------------------------------------------------

class TestDevicePopulations:
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    def setup_method(self):
        _reset_hierarchy()
        _seed_standard_hierarchy()
        # p-alpha-t2 holds exactly one active device, p-alpha-t2-d1.
        _set_transformer_status("p-alpha-t2", "inactive")

    def test_administration_counts_use_the_managed_rtl_population(self):
        # The device stays administratively active, so it stays managed.
        assert repo.count_device_assignments().total_devices == 4

    def test_device_management_table_uses_the_managed_rtl_population(self):
        assert len(repo.list_all_devices()) == 4

    def test_monitoring_counts_use_the_monitoring_device_population(self):
        # count_hierarchy_by_plant backs the Fleet Overview's device column.
        counts = repo.count_hierarchy_by_plant()

        assert sum(devices for _transformers, devices in counts.values()) == 3

    def test_monitoring_freshness_uses_the_monitoring_device_population(self):
        rows = repo.latest_reading_times(["temperature"])

        assert {r.device_id for r in rows} == {
            "p-alpha-t1-d1", "p-alpha-t1-d2", "p-bravo-t1-d1",
        }

    def test_the_two_populations_differ_by_exactly_that_device(self):
        managed = {d.device_id for d in repo.list_all_devices()}
        monitored = {r.device_id for r in repo.latest_reading_times(["temperature"])}

        assert managed - monitored == {"p-alpha-t2-d1"}

    def test_unassigned_rows_still_surface_the_device(self):
        # An RTL parked under an inactive transformer is still an RTL nobody
        # is responsible for; hiding it from the exception list would lose it.
        rows = repo.list_unassigned_devices()

        assert "p-alpha-t2-d1" in [r.device_id for r in rows]

    def test_registration_count_still_includes_the_device(self):
        _seed_device(
            "p-alpha-t2-d9", "p-alpha-t2", "40099", created_at=NOW - timedelta(days=1),
        )

        assert repo.count_devices_registered_between(
            NOW - timedelta(days=7), NOW
        ) == 1

    def test_deactivating_the_device_removes_it_from_both_populations(self):
        with session_scope() as session:
            session.execute(
                text(
                    f"UPDATE {repo._SCHEMA}.devices SET status = 'inactive' "
                    f"WHERE device_id = 'p-alpha-t2-d1'"
                )
            )

        assert repo.count_device_assignments().total_devices == 3
        assert len(repo.list_all_devices()) == 3


# ---------------------------------------------------------------------------
# Repository — active technician count
# ---------------------------------------------------------------------------

class TestCountActiveTechnicians:
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    def setup_method(self):
        _reset_hierarchy()

    def test_no_users_reports_zero(self):
        assert repo.count_active_technicians() == 0

    def test_active_technician_is_counted(self):
        _seed_user("tech-a", "technician", status="active")

        assert repo.count_active_technicians() == 1

    def test_several_active_technicians_are_counted(self):
        _seed_user("tech-a", "technician")
        _seed_user("tech-b", "technician")
        _seed_user("tech-c", "technician")

        assert repo.count_active_technicians() == 3

    def test_inactive_technician_is_excluded(self):
        _seed_user("tech-a", "technician", status="inactive")

        assert repo.count_active_technicians() == 0

    def test_administrator_is_excluded(self):
        _seed_user("admin-a", "administrator", status="active")

        assert repo.count_active_technicians() == 0

    def test_general_user_is_excluded(self):
        _seed_user("general-a", "general", status="active")

        assert repo.count_active_technicians() == 0

    def test_only_active_technicians_are_counted_among_a_mixed_roster(self):
        _seed_user("tech-a", "technician", status="active")
        _seed_user("tech-b", "technician", status="active")
        _seed_user("tech-c", "technician", status="inactive")
        _seed_user("admin-a", "administrator", status="active")
        _seed_user("general-a", "general", status="active")

        assert repo.count_active_technicians() == 2

    def test_agrees_with_the_technician_options_the_assignment_ui_offers(self):
        # The count and the assignment dropdown must never disagree about
        # who is an available technician.
        _seed_user("tech-a", "technician", status="active")
        _seed_user("tech-b", "technician", status="inactive")
        _seed_user("admin-a", "administrator", status="active")

        from services.prototype_users import get_technician_options

        assert repo.count_active_technicians() == len(get_technician_options())


# ---------------------------------------------------------------------------
# Repository — registration window
#
# The window is a closed interval [start, end], matching the inclusive
# convention `get_readings_in_range` already uses for time bounds.
# ---------------------------------------------------------------------------

class TestCountDevicesRegisteredBetween:
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    #: The seven-day window under test, stated once and explicitly.
    WINDOW_START = NOW - timedelta(days=7)
    WINDOW_END = NOW

    def setup_method(self):
        _reset_hierarchy()
        _seed_plant("p-alpha", "Alpha Plant")
        _seed_transformer("p-alpha-t1", "p-alpha", "al01")

    def _count(self, **kwargs) -> int:
        return repo.count_devices_registered_between(
            self.WINDOW_START, self.WINDOW_END, **kwargs
        )

    def test_no_devices_reports_zero(self):
        assert self._count() == 0

    def test_device_created_inside_the_window_is_counted(self):
        _seed_device("d1", "p-alpha-t1", "40001", created_at=NOW - timedelta(days=1))

        assert self._count() == 1

    def test_device_created_exactly_at_the_window_start_is_counted(self):
        # Inclusive lower bound: a device registered exactly seven days ago
        # is still inside "the previous 7 x 24 hours".
        _seed_device("d1", "p-alpha-t1", "40001", created_at=self.WINDOW_START)

        assert self._count() == 1

    def test_device_created_one_second_before_the_window_is_excluded(self):
        _seed_device(
            "d1", "p-alpha-t1", "40001",
            created_at=self.WINDOW_START - timedelta(seconds=1),
        )

        assert self._count() == 0

    def test_device_created_exactly_at_the_window_end_is_counted(self):
        # Inclusive upper bound, same convention as the lower bound.
        _seed_device("d1", "p-alpha-t1", "40001", created_at=self.WINDOW_END)

        assert self._count() == 1

    def test_device_created_after_the_window_end_is_excluded(self):
        # A future-dated created_at (clock skew, or hand-edited data) must
        # not inflate "recently registered": the window is a closed
        # interval, not "anything newer than seven days ago".
        _seed_device(
            "d1", "p-alpha-t1", "40001",
            created_at=self.WINDOW_END + timedelta(seconds=1),
        )

        assert self._count() == 0

    def test_older_device_is_excluded(self):
        _seed_device("d1", "p-alpha-t1", "40001", created_at=NOW - timedelta(days=30))

        assert self._count() == 0

    def test_counts_only_the_devices_inside_the_window(self):
        _seed_device("d1", "p-alpha-t1", "40001", created_at=NOW - timedelta(hours=1))
        _seed_device("d2", "p-alpha-t1", "40002", created_at=NOW - timedelta(days=6))
        _seed_device("d3", "p-alpha-t1", "40003", created_at=NOW - timedelta(days=8))
        _seed_device("d4", "p-alpha-t1", "40004", created_at=NOW - timedelta(days=365))

        assert self._count() == 2

    def test_inactive_device_is_excluded_by_default(self):
        _seed_device(
            "d1", "p-alpha-t1", "40001",
            status="inactive", created_at=NOW - timedelta(days=1),
        )

        assert self._count() == 0

    def test_inactive_device_is_included_on_request(self):
        _seed_device(
            "d1", "p-alpha-t1", "40001",
            status="inactive", created_at=NOW - timedelta(days=1),
        )

        assert self._count(include_inactive=True) == 1

    def test_a_device_registered_through_the_service_lands_in_the_window(self):
        # created_at is defaulted by the database, not by application code;
        # this proves the column the window reads is the one registration
        # actually populates.
        #
        # The window is taken from the DATABASE clock for the same reason.
        # Bounding a database-generated timestamp with `datetime.now()` on the
        # host compares two clocks: when the container runs a few milliseconds
        # ahead, the row falls outside the interval that was meant to contain
        # it and this test fails intermittently. One clock domain, no tolerance
        # window — widening the bound would hide the mismatch rather than
        # remove it.
        from services.device_registration import register_device

        device = register_device("p-alpha-t1", "40009")
        db_now = _database_now()

        assert repo.get_device(device.device_id) is not None
        assert repo.count_devices_registered_between(
            db_now - timedelta(days=7), db_now
        ) == 1


# ---------------------------------------------------------------------------
# Repository — unassigned device rows
# ---------------------------------------------------------------------------

class TestListUnassignedDevices:
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    #: Ordering the projection must produce for `_seed_standard_hierarchy`:
    #: plant name, then transformer code, then device code. Deliberately not
    #: insertion order — Bravo Plant is seeded first and must sort last.
    EXPECTED_ORDER = [
        "p-alpha-t1-d1",
        "p-alpha-t1-d2",
        "p-alpha-t2-d1",
        "p-bravo-t1-d1",
    ]

    def setup_method(self):
        _reset_hierarchy()
        _seed_standard_hierarchy()

    def test_no_devices_returns_empty(self):
        _reset_hierarchy()

        assert repo.list_unassigned_devices() == []

    def test_all_devices_are_listed_when_nothing_is_assigned(self):
        rows = repo.list_unassigned_devices()

        assert [r.device_id for r in rows] == self.EXPECTED_ORDER

    def test_assigned_device_is_excluded(self):
        _seed_user("tech-a", "technician")
        repo.assign_device_to_user("p-alpha-t1-d1", "tech-a")

        rows = repo.list_unassigned_devices()

        assert [r.device_id for r in rows] == [
            "p-alpha-t1-d2", "p-alpha-t2-d1", "p-bravo-t1-d1",
        ]

    def test_device_whose_assignment_ended_is_listed_again(self):
        _seed_user("tech-a", "technician")
        repo.assign_device_to_user("p-alpha-t1-d1", "tech-a")
        repo.end_active_device_assignment("p-alpha-t1-d1")

        rows = repo.list_unassigned_devices()

        assert [r.device_id for r in rows] == self.EXPECTED_ORDER

    def test_reassigned_device_is_still_excluded_exactly_once(self):
        _seed_user("tech-a", "technician")
        _seed_user("tech-b", "technician")
        repo.assign_device_to_user("p-alpha-t1-d1", "tech-a")
        repo.assign_device_to_user("p-alpha-t1-d1", "tech-b")

        rows = repo.list_unassigned_devices()

        assert "p-alpha-t1-d1" not in [r.device_id for r in rows]
        assert len(rows) == 3

    def test_row_carries_device_identity_and_rtl_uid(self):
        row = next(r for r in repo.list_unassigned_devices()
                   if r.device_id == "p-alpha-t1-d1")

        assert row.device_id == "p-alpha-t1-d1"
        assert row.device_code == "40002"

    def test_row_carries_transformer_context(self):
        row = next(r for r in repo.list_unassigned_devices()
                   if r.device_id == "p-alpha-t1-d1")

        assert row.transformer_id == "p-alpha-t1"
        assert row.transformer_code == "al01"

    def test_row_carries_plant_context(self):
        row = next(r for r in repo.list_unassigned_devices()
                   if r.device_id == "p-alpha-t1-d1")

        assert row.plant_id == "p-alpha"
        assert row.plant_name == "Alpha Plant"

    def test_row_carries_administrative_status(self):
        row = next(r for r in repo.list_unassigned_devices()
                   if r.device_id == "p-alpha-t1-d1")

        assert row.status == "active"

    def test_rows_are_the_same_shape_the_device_admin_table_already_uses(self):
        rows = repo.list_unassigned_devices()

        assert all(isinstance(r, repo.AdminDeviceRow) for r in rows)

    def test_limit_returns_the_first_rows_in_order(self):
        rows = repo.list_unassigned_devices(limit=2)

        assert [r.device_id for r in rows] == self.EXPECTED_ORDER[:2]

    def test_limit_larger_than_the_population_returns_everything(self):
        rows = repo.list_unassigned_devices(limit=99)

        assert [r.device_id for r in rows] == self.EXPECTED_ORDER

    def test_limit_of_zero_returns_nothing(self):
        assert repo.list_unassigned_devices(limit=0) == []

    def test_omitting_the_limit_returns_everything(self):
        assert len(repo.list_unassigned_devices()) == 4

    def test_negative_limit_is_rejected_before_reaching_sql(self):
        # LIMIT -1 is a PostgreSQL error; a caller bug must surface as a
        # plain ValueError, never as a database error carrying SQL text.
        with pytest.raises(ValueError):
            repo.list_unassigned_devices(limit=-1)

    def test_inactive_device_is_excluded_by_default(self):
        _seed_device("p-alpha-t2-d2", "p-alpha-t2", "40005", status="inactive")

        rows = repo.list_unassigned_devices()

        assert [r.device_id for r in rows] == self.EXPECTED_ORDER

    def test_inactive_device_is_included_on_request(self):
        _seed_device("p-alpha-t2-d2", "p-alpha-t2", "40005", status="inactive")

        rows = repo.list_unassigned_devices(include_inactive=True)

        assert "p-alpha-t2-d2" in [r.device_id for r in rows]

    def test_row_count_agrees_with_the_unassigned_count(self):
        _seed_user("tech-a", "technician")
        repo.assign_device_to_user("p-bravo-t1-d1", "tech-a")

        rows = repo.list_unassigned_devices()
        counts = repo.count_device_assignments()

        assert len(rows) == counts.unassigned_devices


# ---------------------------------------------------------------------------
# Service — the registration window (pure, no database)
# ---------------------------------------------------------------------------

class TestRegistrationWindow:
    def test_window_is_seven_days(self):
        assert admin_overview.RECENT_REGISTRATION_WINDOW == timedelta(days=7)

    def test_window_is_the_seven_days_before_the_supplied_instant(self):
        start, end = admin_overview.registration_window(NOW)

        assert end == NOW
        assert start == NOW - timedelta(days=7)

    def test_window_spans_exactly_seven_times_twenty_four_hours(self):
        start, end = admin_overview.registration_window(NOW)

        assert end - start == timedelta(hours=7 * 24)

    def test_window_uses_the_supplied_instant_not_the_wall_clock(self):
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)

        start, end = admin_overview.registration_window(past)

        assert end == past
        assert start == datetime(2019, 12, 25, tzinfo=timezone.utc)

    def test_window_falls_back_to_now_when_no_instant_is_supplied(self):
        before = datetime.now(timezone.utc)
        start, end = admin_overview.registration_window()
        after = datetime.now(timezone.utc)

        assert before <= end <= after
        assert end - start == timedelta(days=7)


# ---------------------------------------------------------------------------
# Service — composition (no database; the repository boundary is substituted
# so this asserts what the service does with results, not what SQL returns)
# ---------------------------------------------------------------------------

def _row(device_id: str) -> repo.AdminDeviceRow:
    return repo.AdminDeviceRow(
        device_id=device_id,
        device_code="40001",
        status="active",
        transformer_id="t1",
        transformer_code="al01",
        plant_id="p1",
        plant_name="Alpha Plant",
    )


class _StubRepo:
    """Records the arguments the service passes down, and returns fixed
    results so the composition can be asserted on its own.
    """

    def __init__(self, counts, technicians, registered, rows):
        self._counts = counts
        self._technicians = technicians
        self._registered = registered
        self._rows = rows
        self.calls: dict = {}

    def count_device_assignments(self, include_inactive=False):
        self.calls["count_device_assignments"] = {"include_inactive": include_inactive}
        return self._counts

    def count_active_technicians(self):
        self.calls["count_active_technicians"] = {}
        return self._technicians

    def count_devices_registered_between(self, start, end, include_inactive=False):
        self.calls["count_devices_registered_between"] = {
            "start": start, "end": end, "include_inactive": include_inactive,
        }
        return self._registered

    def list_unassigned_devices(self, limit=None, include_inactive=False):
        self.calls["list_unassigned_devices"] = {
            "limit": limit, "include_inactive": include_inactive,
        }
        return self._rows


@pytest.fixture
def stub_repo(monkeypatch):
    stub = _StubRepo(
        counts=repo.DeviceAssignmentCounts(
            total_devices=120, assigned_devices=7, unassigned_devices=113
        ),
        technicians=3,
        registered=4,
        rows=[_row("d1"), _row("d2")],
    )
    monkeypatch.setattr(admin_overview, "repo", stub)
    return stub


class TestAdminOverviewComposition:
    def test_summary_carries_the_device_counts(self, stub_repo):
        summary = admin_overview.get_admin_overview(now=NOW)

        assert summary.total_devices == 120
        assert summary.assigned_devices == 7
        assert summary.unassigned_devices == 113

    def test_summary_carries_the_active_technician_count(self, stub_repo):
        summary = admin_overview.get_admin_overview(now=NOW)

        assert summary.active_technicians == 3

    def test_summary_carries_the_recently_registered_count(self, stub_repo):
        summary = admin_overview.get_admin_overview(now=NOW)

        assert summary.recently_registered_devices == 4

    def test_summary_carries_the_unassigned_rows(self, stub_repo):
        summary = admin_overview.get_admin_overview(now=NOW)

        assert [r.device_id for r in summary.unassigned_rows] == ["d1", "d2"]

    def test_registration_count_uses_the_seven_day_window_from_the_supplied_now(
        self, stub_repo
    ):
        admin_overview.get_admin_overview(now=NOW)

        call = stub_repo.calls["count_devices_registered_between"]
        assert call["start"] == NOW - timedelta(days=7)
        assert call["end"] == NOW

    def test_default_unassigned_row_limit_is_applied(self, stub_repo):
        admin_overview.get_admin_overview(now=NOW)

        assert stub_repo.calls["list_unassigned_devices"]["limit"] == (
            admin_overview.DEFAULT_UNASSIGNED_ROW_LIMIT
        )

    def test_default_unassigned_row_limit_is_five(self):
        assert admin_overview.DEFAULT_UNASSIGNED_ROW_LIMIT == 5

    def test_unassigned_row_limit_can_be_overridden(self, stub_repo):
        admin_overview.get_admin_overview(now=NOW, unassigned_limit=2)

        assert stub_repo.calls["list_unassigned_devices"]["limit"] == 2

    def test_active_only_population_by_default(self, stub_repo):
        admin_overview.get_admin_overview(now=NOW)

        assert stub_repo.calls["count_device_assignments"]["include_inactive"] is False
        assert stub_repo.calls["list_unassigned_devices"]["include_inactive"] is False
        assert (
            stub_repo.calls["count_devices_registered_between"]["include_inactive"]
            is False
        )

    def test_inactive_equipment_can_be_included(self, stub_repo):
        admin_overview.get_admin_overview(now=NOW, include_inactive=True)

        assert stub_repo.calls["count_device_assignments"]["include_inactive"] is True
        assert stub_repo.calls["list_unassigned_devices"]["include_inactive"] is True

    def test_summary_is_immutable(self, stub_repo):
        summary = admin_overview.get_admin_overview(now=NOW)

        with pytest.raises(FrozenInstanceError):
            summary.total_devices = 0

    def test_unassigned_rows_are_immutable(self, stub_repo):
        summary = admin_overview.get_admin_overview(now=NOW)

        assert isinstance(summary.unassigned_rows, tuple)

    def test_each_repository_query_runs_exactly_once(self, stub_repo):
        admin_overview.get_admin_overview(now=NOW)

        assert set(stub_repo.calls) == {
            "count_device_assignments",
            "count_active_technicians",
            "count_devices_registered_between",
            "list_unassigned_devices",
        }


# ---------------------------------------------------------------------------
# Service — against the real database
# ---------------------------------------------------------------------------

class TestAdminOverviewAgainstDatabase:
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    def setup_method(self):
        _reset_hierarchy()
        _seed_standard_hierarchy()

    def test_empty_fleet_reports_zeros_truthfully(self):
        _reset_hierarchy()

        summary = admin_overview.get_admin_overview(now=NOW)

        assert summary.total_devices == 0
        assert summary.assigned_devices == 0
        assert summary.unassigned_devices == 0
        assert summary.active_technicians == 0
        assert summary.recently_registered_devices == 0
        assert summary.unassigned_rows == ()

    def test_unassigned_fleet_with_no_technicians_reports_that_truthfully(self):
        # The honest "nothing is set up yet" state: every device unassigned,
        # no technicians. Nothing is invented to make the figure look better.
        summary = admin_overview.get_admin_overview(now=NOW)

        assert summary.total_devices == 4
        assert summary.assigned_devices == 0
        assert summary.unassigned_devices == 4
        assert summary.active_technicians == 0

    def test_summary_reflects_real_assignments(self):
        _seed_user("tech-a", "technician")
        _seed_user("tech-b", "technician", status="inactive")
        repo.assign_device_to_user("p-alpha-t1-d1", "tech-a")

        summary = admin_overview.get_admin_overview(now=NOW)

        assert summary.assigned_devices == 1
        assert summary.unassigned_devices == 3
        assert summary.active_technicians == 1

    def test_unassigned_rows_respect_the_limit_and_the_ordering(self):
        summary = admin_overview.get_admin_overview(now=NOW, unassigned_limit=2)

        assert [r.device_id for r in summary.unassigned_rows] == [
            "p-alpha-t1-d1", "p-alpha-t1-d2",
        ]

    def test_recently_registered_uses_created_at_against_the_supplied_now(self):
        _seed_device("d-new", "p-alpha-t1", "40010", created_at=NOW - timedelta(days=2))
        _seed_device("d-old", "p-alpha-t1", "40011", created_at=NOW - timedelta(days=20))

        summary = admin_overview.get_admin_overview(now=NOW)

        # The four standard devices are created at the real wall clock, which
        # is far from NOW, so only the explicitly dated recent device counts.
        assert summary.recently_registered_devices == 1

    def test_counts_and_rows_describe_the_same_fleet(self):
        _seed_user("tech-a", "technician")
        repo.assign_device_to_user("p-bravo-t1-d1", "tech-a")

        summary = admin_overview.get_admin_overview(now=NOW, unassigned_limit=None)

        assert len(summary.unassigned_rows) == summary.unassigned_devices
        assert summary.assigned_devices + summary.unassigned_devices == (
            summary.total_devices
        )
