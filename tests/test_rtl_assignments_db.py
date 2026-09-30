"""ADR-032: application-owned client-RTL Technician assignments (database-backed).

Runs against the disposable `isolated_schema`; never the real schema, and never
the client SQL Server (a fake source stands in for it).
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from config import audit as audit_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from repositories.rtl_assignment_source_repository import ClientPerson, LegacyAssignmentRow
from services import rtl_assignment_bootstrap as boot
from services import rtl_assignment_service as svc
from services import rtl_scope
from services.auth_service import AuthenticatedUser
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

REGISTERED = set(range(29000, 29100))


def registered() -> set[int]:
    return set(REGISTERED)


def _user(username: str, role: str, status: str = "active", person_id: int | None = None) -> int:
    uid = repo.create_or_update_user(
        username=username, full_name=username.title(), role=role, status=status
    ).user_id
    if person_id is not None:
        with session_scope() as s:
            s.execute(text(f"UPDATE {repo._SCHEMA}.users SET client_person_id = :p WHERE user_id = :u"),
                      {"p": person_id, "u": uid})
    return uid


def _auth(user_id: int, role: str) -> AuthenticatedUser:
    return AuthenticatedUser(user_id=user_id, username="x", full_name="X", role=role)


def _rows(uid: int | None = None):
    sql = f"SELECT * FROM {repo._SCHEMA}.rtl_technician_assignments"
    if uid is not None:
        sql += f" WHERE device_uid = {int(uid)}"
    with session_scope() as s:
        return [dict(r) for r in s.execute(text(sql + " ORDER BY assignment_id")).mappings().all()]


def _audit():
    with session_scope() as s:
        return [dict(r) for r in s.execute(text(
            f"SELECT operation, entity_type, entity_id, user_id, old_values, new_values "
            f"FROM {repo._SCHEMA}.audit_log ORDER BY audit_id")).mappings().all()]


@pytest.fixture(autouse=True)
def clean():
    repo.delete_all_users()
    yield
    repo.delete_all_users()


@pytest.fixture()
def people():
    return {
        "admin": _user("adm", "administrator"),
        "general": _user("gen", "general"),
        "a": _user("tech-a", "technician"),
        "b": _user("tech-b", "technician"),
        "inactive": _user("tech-off", "technician", status="inactive"),
    }


def assign(uid, tech, actor, **kw):
    return svc.assign(uid, tech, actor=actor, registered_fetch=registered, **kw)


def reassign(uid, tech, expected, actor):
    return svc.reassign(uid, tech, expected_assignment_id=expected, actor=actor,
                        registered_fetch=registered)


# -------------------------------------------------------------------- assign
class TestAssign:
    def test_an_administrator_assigns_an_unassigned_registered_rtl(self, people):
        new_id = assign(29001, people["a"], _auth(people["admin"], ADMINISTRATOR))
        (row,) = _rows(29001)
        assert row["assignment_id"] == new_id and row["ended_at"] is None
        assert row["technician_user_id"] == people["a"]
        assert row["provenance"] == "APPLICATION"
        assert row["assigned_at"] is not None and row["assigned_by"] == people["admin"]
        assert row["imported_at"] is None

    def test_the_audit_row_records_actor_uid_and_technician(self, people):
        assign(29001, people["a"], _auth(people["admin"], ADMINISTRATOR))
        (a,) = _audit()
        assert a["operation"] == audit_cfg.RTL_ASSIGNMENT_CREATED
        assert a["entity_type"] == audit_cfg.ENTITY_RTL_ASSIGNMENT and a["entity_id"] == "29001"
        assert a["user_id"] == people["admin"]
        assert a["new_values"]["technician_user_id"] == people["a"]
        assert "email" not in str(a["new_values"]).lower() and "mobile" not in str(a["new_values"]).lower()

    def test_many_rtls_per_technician(self, people):
        for uid in (29001, 29002, 29003):
            assign(uid, people["a"], _auth(people["admin"], ADMINISTRATOR))
        assert repo.list_current_rtl_assignment_uids(people["a"]) == [29001, 29002, 29003]

    @pytest.mark.parametrize("role", [TECHNICIAN, GENERAL])
    def test_only_an_administrator_may_assign(self, people, role):
        with pytest.raises(svc.NotAuthorized):
            assign(29001, people["a"], _auth(people["a"], role))
        with pytest.raises(svc.NotAuthorized):
            assign(29001, people["a"], None)
        assert _rows() == []

    def test_the_rtl_must_be_registered(self, people):
        with pytest.raises(svc.RtlNotRegistered):
            assign(12345, people["a"], _auth(people["admin"], ADMINISTRATOR))
        assert _rows() == []

    def test_the_target_must_be_an_active_technician(self, people):
        admin = _auth(people["admin"], ADMINISTRATOR)
        for bad in (people["admin"], people["general"], people["inactive"], 999999):
            with pytest.raises(svc.NotATechnician):
                assign(29001, bad, admin)
        assert _rows() == []

    def test_assigning_an_already_assigned_rtl_is_refused(self, people):
        admin = _auth(people["admin"], ADMINISTRATOR)
        assign(29001, people["a"], admin)
        with pytest.raises(svc.AlreadyAssigned):
            assign(29001, people["b"], admin)
        with pytest.raises(svc.AlreadyAssigned):  # duplicate submission
            assign(29001, people["a"], admin)
        assert len(_rows(29001)) == 1 and len(_audit()) == 1


# ------------------------------------------------------------------ reassign
class TestReassign:
    def _assigned(self, people):
        admin = _auth(people["admin"], ADMINISTRATOR)
        return admin, assign(29001, people["a"], admin)

    def test_reassignment_is_atomic_and_history_is_retained(self, people):
        admin, first = self._assigned(people)
        second = reassign(29001, people["b"], first, admin)
        old, new = _rows(29001)
        assert old["assignment_id"] == first and old["ended_at"] is not None
        assert old["ended_by"] == people["admin"]
        assert old["technician_user_id"] == people["a"]  # never overwritten
        assert new["assignment_id"] == second and new["ended_at"] is None
        assert new["technician_user_id"] == people["b"] and new["assigned_by"] == people["admin"]
        assert sum(r["ended_at"] is None for r in _rows(29001)) == 1

    def test_scope_follows_the_current_assignment_and_history_never_grants(self, people):
        admin, first = self._assigned(people)
        reassign(29001, people["b"], first, admin)
        assert rtl_scope.scope_for(_auth(people["a"], TECHNICIAN)).uids == frozenset()
        assert rtl_scope.scope_for(_auth(people["b"], TECHNICIAN)).uids == frozenset({29001})

    def test_the_audit_trail_ends_then_reassigns(self, people):
        admin, first = self._assigned(people)
        reassign(29001, people["b"], first, admin)
        ops = [a["operation"] for a in _audit()]
        assert ops == [audit_cfg.RTL_ASSIGNMENT_CREATED, audit_cfg.RTL_ASSIGNMENT_ENDED,
                       audit_cfg.RTL_ASSIGNMENT_REASSIGNED]
        reassigned = _audit()[-1]
        assert reassigned["old_values"]["technician_user_id"] == people["a"]
        assert reassigned["new_values"]["technician_user_id"] == people["b"]
        assert reassigned["user_id"] == people["admin"]

    def test_reassigning_to_the_same_technician_changes_nothing(self, people):
        admin, first = self._assigned(people)
        with pytest.raises(svc.SameTechnician):
            reassign(29001, people["a"], first, admin)
        assert len(_rows(29001)) == 1 and len(_audit()) == 1

    def test_a_stale_view_cannot_reassign(self, people):
        admin, first = self._assigned(people)
        reassign(29001, people["b"], first, admin)  # someone else moves it first
        with pytest.raises(svc.StaleAssignment):
            reassign(29001, people["a"], first, admin)  # stale id from the old page
        assert sum(r["ended_at"] is None for r in _rows(29001)) == 1

    def test_an_unassigned_rtl_cannot_be_reassigned(self, people):
        admin = _auth(people["admin"], ADMINISTRATOR)
        with pytest.raises(svc.StaleAssignment):
            reassign(29001, people["b"], 1, admin)

    def test_only_an_administrator_may_reassign(self, people):
        admin, first = self._assigned(people)
        with pytest.raises(svc.NotAuthorized):
            reassign(29001, people["b"], first, _auth(people["a"], TECHNICIAN))
        assert _rows(29001)[0]["ended_at"] is None

    def test_concurrent_reassignments_leave_exactly_one_open_assignment(self, people):
        admin, first = self._assigned(people)
        gate = threading.Barrier(2)
        third = _user("tech-c", "technician")

        def attempt(target):
            gate.wait()
            try:
                reassign(29001, target, first, admin)
                return "ok"
            except svc.AssignmentError:
                return "refused"

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(attempt, (people["b"], third)))
        assert sorted(results) == ["ok", "refused"]
        assert sum(r["ended_at"] is None for r in _rows(29001)) == 1

    def test_ending_an_assignment_retains_history(self, people):
        admin, first = self._assigned(people)
        svc.end_assignment(29001, expected_assignment_id=first, actor=admin)
        (row,) = _rows(29001)
        assert row["ended_at"] is not None and row["ended_by"] == people["admin"]
        assert repo.list_current_rtl_assignments() == []
        assert _audit()[-1]["operation"] == audit_cfg.RTL_ASSIGNMENT_ENDED
        assign(29001, people["b"], admin)  # can be assigned again afterwards
        assert len(_rows(29001)) == 2


# ---------------------------------------------------------- database constraints
class TestDatabaseRules:
    def _insert(self, **cols):
        cols = {"device_uid": 29001, "provenance": "APPLICATION", **cols}
        names = ", ".join(cols)
        marks = ", ".join(f":{k}" for k in cols)
        with session_scope() as s:
            s.execute(text(f"INSERT INTO {repo._SCHEMA}.rtl_technician_assignments ({names}) "
                           f"VALUES ({marks})"), cols)

    def test_two_open_rows_for_one_rtl_are_impossible(self, people):
        base = dict(technician_user_id=people["a"], assigned_by=people["admin"], assigned_at="2026-01-01")
        self._insert(**base)
        with pytest.raises(IntegrityError):
            self._insert(**{**base, "technician_user_id": people["b"]})

    def test_many_closed_rows_for_one_rtl_are_allowed(self, people):
        for tech in (people["a"], people["b"], people["a"]):
            self._insert(technician_user_id=tech, assigned_by=people["admin"],
                         assigned_at="2026-01-01", ended_at="2026-02-01", ended_by=people["admin"])
        assert len(_rows(29001)) == 3

    def test_a_legacy_row_cannot_carry_an_invented_date_or_actor(self, people):
        with pytest.raises(IntegrityError):
            self._insert(technician_user_id=people["a"], provenance="LEGACY_IMPORT",
                         assigned_at="2020-01-01", imported_at="2026-09-30")
        with pytest.raises(IntegrityError):
            self._insert(technician_user_id=people["a"], provenance="LEGACY_IMPORT",
                         assigned_by=people["admin"], imported_at="2026-09-30")

    def test_an_application_row_needs_a_date_and_an_actor(self, people):
        with pytest.raises(IntegrityError):
            self._insert(technician_user_id=people["a"], assigned_at="2026-01-01")

    def test_unknown_provenance_and_bad_uid_are_refused(self, people):
        with pytest.raises(IntegrityError):
            self._insert(technician_user_id=people["a"], provenance="MAGIC", imported_at="2026-01-01")
        with pytest.raises(IntegrityError):
            self._insert(technician_user_id=people["a"], device_uid=0, provenance="LEGACY_IMPORT",
                         imported_at="2026-01-01")

    def test_client_person_id_is_unique_where_set(self):
        _user("p1", "technician", person_id=5)
        with pytest.raises(IntegrityError):
            _user("p2", "technician", person_id=5)


# ------------------------------------------------------------------ overview
class TestOverview:
    def test_assigned_and_unassigned_rows_and_filters(self, people):
        admin = _auth(people["admin"], ADMINISTRATOR)
        assign(29001, people["a"], admin)
        assign(29002, people["b"], admin)

        class Row:
            def __init__(self, u):
                self.device_uid, self.mapping_codes = u, ("TA",) if u == 29001 else ()

        class Net:
            status = svc.network.NetworkStatus.DATA
            rows = [Row(u) for u in (29001, 29002, 29003, 29004)]

        overview = svc.get_assignment_overview(network_fetch=lambda: Net)
        assert overview.assigned_count == 2 and overview.unassigned_count == 2
        rows = overview.rows
        assert [r.device_uid for r in svc.filter_rows(rows, view="unassigned")] == [29003, 29004]
        assert [r.device_uid for r in svc.filter_rows(rows, view="assigned")] == [29001, 29002]
        assert [r.device_uid for r in svc.filter_rows(rows, technician_user_id=people["b"])] == [29002]
        assert [r.device_uid for r in svc.filter_rows(rows, uid_text="2900")] == [29001, 29002, 29003, 29004]
        assert [r.device_uid for r in svc.filter_rows(rows, uid_text="29003")] == [29003]
        assert svc.from_payload(svc.to_payload(rows)) == rows  # store round-trip

    def test_history_lists_every_assignment(self, people):
        admin = _auth(people["admin"], ADMINISTRATOR)
        first = assign(29001, people["a"], admin)
        reassign(29001, people["b"], first, admin)
        history = svc.get_assignment_history(29001)
        assert [h.technician_name for h in history] == ["Tech-B", "Tech-A"]
        assert history[0].is_current and not history[1].is_current
        assert history[0].assigned_by_name == "Adm"


# ----------------------------------------------------- legacy import bootstrap
TECH_NAMES = {2: "Senzo Mpungose", 3: "Reginald Tshabalala", 4: "Nhlakanipho Ndwandwe",
              5: "Shawn Papi", 6: "Linda Gerotek"}


class FakeSource:
    """Stands in for the read-only client SQL Server (never written)."""

    def __init__(self, legacy, technicians=None, extra_people=()):
        self.legacy = legacy
        self.technicians = [ClientPerson(i, n) for i, n in (technicians or TECH_NAMES).items()]
        self.people = self.technicians + [ClientPerson(1, "Some Admin")] + list(extra_people)

    def get_legacy_assignments(self): return list(self.legacy)
    def get_technician_persons(self): return list(self.technicians)
    def get_all_persons(self): return list(self.people)


def legacy_fixture():
    """68 legacy rows: 64 on registered UIDs, 4 on historical/unregistered ones."""
    names = list(TECH_NAMES.values())
    rows = [LegacyAssignmentRow(names[i % 5], 29000 + i) for i in range(64)]
    rows += [LegacyAssignmentRow(names[0], uid) for uid in (28001, 28002, 28003, 28004)]
    return rows


def plan_for(source, **kw):
    return boot.build_plan(source=source, registered_fetch=registered, **kw)


class TestLegacyBootstrap:
    def test_preview_recognises_64_current_and_excludes_4_historical(self):
        plan = plan_for(FakeSource(legacy_fixture()))
        assert plan.ok and len(plan.candidates) == 64
        assert [r.device_uid for r in plan.excluded_unregistered] == [28001, 28002, 28003, 28004]
        assert len(plan.needs_provisioning) == 5  # no application users yet
        assert repo.count_current_rtl_assignments() == 0  # preview wrote nothing
        assert _rows() == []

    def test_apply_needs_explicit_provisioning_when_users_are_missing(self):
        plan = plan_for(FakeSource(legacy_fixture()))
        with pytest.raises(boot.BootstrapRefused):
            boot.apply_plan(plan)
        assert _rows() == []

    def test_apply_imports_with_legacy_provenance_and_no_invented_history(self):
        plan = plan_for(FakeSource(legacy_fixture()))
        assert boot.apply_plan(plan, provision=True) == {"imported": 64, "provisioned_users": 5}
        rows = _rows()
        assert len(rows) == 64
        assert {r["provenance"] for r in rows} == {"LEGACY_IMPORT"}
        assert all(r["assigned_at"] is None and r["assigned_by"] is None for r in rows)
        assert all(r["imported_at"] is not None and r["ended_at"] is None for r in rows)
        assert not any(r["device_uid"] in (28001, 28002, 28003, 28004) for r in rows)
        assert not any(u in {r["device_uid"] for r in rows} for u in range(29064, 29100))

    def test_provisioned_technicians_are_login_less_and_bound_to_the_client_person(self):
        boot.apply_plan(plan_for(FakeSource(legacy_fixture())), provision=True)
        users = repo.list_user_ids_by_client_person_id()
        assert set(users) == set(TECH_NAMES)
        assert all(u.role == "technician" for u in repo.list_users())

    def test_rerunning_is_idempotent(self):
        boot.apply_plan(plan_for(FakeSource(legacy_fixture())), provision=True)
        second = plan_for(FakeSource(legacy_fixture()))
        assert second.ok and second.candidates == [] and len(second.already_present) == 64
        assert boot.apply_plan(second, provision=True) == {"imported": 0, "provisioned_users": 0}
        assert len(_rows()) == 64 and len(repo.list_users()) == 5

    def test_imported_assignments_grant_the_mapped_technicians_access(self):
        boot.apply_plan(plan_for(FakeSource(legacy_fixture())), provision=True)
        senzo = repo.list_user_ids_by_client_person_id()[2]
        scope = rtl_scope.scope_for(_auth(senzo, TECHNICIAN))
        assert scope.uids == frozenset(29000 + i for i in range(64) if i % 5 == 0)

    def test_a_conflicting_current_assignment_blocks_the_import(self, people):
        boot.apply_plan(plan_for(FakeSource(legacy_fixture())), provision=True)
        uid = 29000  # legacy Senzo; move it to someone else through the application
        admin = _auth(people["admin"], ADMINISTRATOR)
        current = repo.list_current_rtl_assignments()[0]
        reassign(current.device_uid, people["a"], current.assignment_id, admin)
        plan = plan_for(FakeSource(legacy_fixture()))
        assert not plan.ok
        assert any(str(current.device_uid) in p for p in plan.problems)
        with pytest.raises(boot.BootstrapRefused):
            boot.apply_plan(plan, provision=True)

    def test_an_assignment_an_administrator_ended_is_not_resurrected(self, people):
        boot.apply_plan(plan_for(FakeSource(legacy_fixture())), provision=True)
        admin = _auth(people["admin"], ADMINISTRATOR)
        current = repo.list_current_rtl_assignments()[0]
        svc.end_assignment(current.device_uid, expected_assignment_id=current.assignment_id, actor=admin)
        plan = plan_for(FakeSource(legacy_fixture()))
        assert plan.ok and current.device_uid in plan.skipped_has_history
        assert boot.apply_plan(plan, provision=True)["imported"] == 0
        assert current.device_uid not in {a.device_uid for a in repo.list_current_rtl_assignments()}

    def test_the_275_style_remainder_stays_unassigned_and_is_not_hard_coded(self, people):
        boot.apply_plan(plan_for(FakeSource(legacy_fixture())), provision=True)
        registered_all = sorted(REGISTERED)
        assigned = {a.device_uid for a in repo.list_current_rtl_assignments()}
        unassigned = [u for u in registered_all if u not in assigned]
        assert len(assigned) == 64 and len(unassigned) == len(registered_all) - 64
        # a Technician gains nothing merely because an RTL is unassigned
        for tech in repo.list_user_ids_by_client_person_id().values():
            assert not (rtl_scope.scope_for(_auth(tech, TECHNICIAN)).uids & set(unassigned))

    @pytest.mark.parametrize("mutate,needle", [
        (lambda src: src.legacy.append(LegacyAssignmentRow("Nobody Known", 29070)), "matches no person"),
        (lambda src: src.legacy.append(LegacyAssignmentRow("Some Admin", 29070)), "not a Technician"),
        (lambda src: src.legacy.append(LegacyAssignmentRow("senzo mpungose", 29070)), "matches no person"),
        (lambda src: src.legacy.append(LegacyAssignmentRow("Senzo Mpungose ", 29070)), "matches no person"),
        (lambda src: src.legacy.append(LegacyAssignmentRow("Shawn Papi", 29000)), "more than one Technician"),
        (lambda src: src.legacy.append(src.legacy[0]), "Duplicate legacy pair"),
    ])
    def test_identity_and_data_quality_problems_stop_the_import(self, mutate, needle):
        source = FakeSource(legacy_fixture())
        mutate(source)
        plan = plan_for(source)
        assert not plan.ok and any(needle in p for p in plan.problems), plan.problems
        with pytest.raises(boot.BootstrapRefused):
            boot.apply_plan(plan, provision=True)
        assert _rows() == []

    def test_names_are_matched_exactly_never_by_case_or_trimming(self):
        source = FakeSource([LegacyAssignmentRow("SENZO MPUNGOSE", 29001)])
        plan = plan_for(source)
        assert not plan.ok and plan.candidates == []
