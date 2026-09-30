"""ADR-032: the one client-RTL UID scope, and every real route using it.

Pure logic, no database. Fakes stand in for the client SQL Server repositories
(and for the single assignment read).
"""
from __future__ import annotations

import ast
import re
from datetime import date, datetime
from pathlib import Path

import pytest

from callbacks import fleet_overview, historical_events, rtl_dashboard, rtl_detail, rtl_network
from repositories import rtl_events_repository as events_repo
from services import rtl_dashboard_service as dashboard
from services import rtl_detail_service as detail
from services import rtl_events_service as events
from services import rtl_fleet_service as fleet
from services import rtl_network_service as net
from services import rtl_scope
from services.auth_service import AuthenticatedUser
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN
from services.rtl_scope import DENIED, UNRESTRICTED, RtlScope
from tests.dash_tree import text_of
from tests.test_historical_events import EventsRepo, ev, network_repo
from tests.test_rtl_fleet import FakeRepo, _h, _latest
from tests.test_rtl_network import FakeRepo as NetRepo
from tests.test_rtl_network import M

ROOT = Path(__file__).resolve().parents[1]


def user(role, user_id=7):
    return AuthenticatedUser(user_id=user_id, username="u", full_name="U", role=role)


# ------------------------------------------------------------------ the scope
class TestScopeResolution:
    def test_administrator_and_general_are_unrestricted(self):
        assert rtl_scope.scope_for(user(ADMINISTRATOR)) is UNRESTRICTED
        assert rtl_scope.scope_for(user(GENERAL)) is UNRESTRICTED
        assert UNRESTRICTED.is_unrestricted and UNRESTRICTED.allows(123456)

    def test_a_technician_gets_exactly_their_current_assignments(self, monkeypatch):
        asked = []
        monkeypatch.setattr(
            rtl_scope.repo, "list_current_rtl_assignment_uids",
            lambda user_id: asked.append(user_id) or [29021, 29025],
        )
        scope = rtl_scope.scope_for(user(TECHNICIAN, user_id=42))
        assert asked == [42]  # keyed on the user id, never a name
        assert scope.uids == frozenset({29021, 29025})
        assert scope.allows(29021) and not scope.allows(29022)
        assert not scope.is_unrestricted

    def test_no_session_or_unknown_role_is_denied_not_merely_empty(self):
        for u in (None, user("superuser"), user(None)):
            scope = rtl_scope.scope_for(u)
            assert scope is DENIED
            assert not rtl_scope.may_view_real_rtls(scope) and not scope.allows(1)

    def test_none_is_not_empty(self, monkeypatch):
        """A Technician with no assignments sees nothing - never everything."""
        monkeypatch.setattr(rtl_scope.repo, "list_current_rtl_assignment_uids", lambda _u: [])
        empty = rtl_scope.scope_for(user(TECHNICIAN))
        assert empty.uids == frozenset() and not empty.is_unrestricted
        assert rtl_scope.may_view_real_rtls(empty)  # permitted, sees zero
        assert empty.restrict([1, 2, 3]) == []
        assert UNRESTRICTED.restrict([3, 1, 2]) == [1, 2, 3]
        assert DENIED.restrict([1, 2]) == []

    def test_restrict_only_returns_registered_uids_in_scope(self):
        scope = RtlScope(frozenset({1, 2, 99}))
        assert scope.restrict([3, 2, 1]) == [1, 2]  # 99 is not registered

    def test_filter_rows(self):
        class R:
            def __init__(self, u):
                self.device_uid = u
        rows = [R(1), R(2), R(3)]
        assert [r.device_uid for r in RtlScope(frozenset({2})).filter_rows(rows)] == [2]

    def test_is_assigned_only_only_for_a_restricted_permitted_scope(self):
        assert rtl_scope.is_assigned_only(RtlScope(frozenset({1})))
        assert not rtl_scope.is_assigned_only(UNRESTRICTED)
        assert not rtl_scope.is_assigned_only(DENIED)


# ---------------------------------------------------------------------- Fleet
def _fleet_repo():
    return FakeRepo(
        [1, 2, 3, 4],
        latest={1: _latest(1, "20"), 2: _latest(2, "21"), 3: _latest(3, "22")},
        mappings=[M(1, "TA1"), M(2, "TA2")],
        hierarchy=[_h(1, "TA1"), _h(2, "TA2")],
    )


class TestFleetScope:
    def test_a_technician_fleet_holds_only_assigned_uids_and_counts_follow(self):
        result = fleet.get_real_fleet(_fleet_repo(), scope=RtlScope(frozenset({2, 4})))
        assert [r.device_uid for r in result.rows] == [2, 4]
        s = result.summary
        assert (s.registered, s.mapped, s.with_temperature, s.no_temperature) == (2, 1, 1, 1)

    def test_temperatures_are_only_requested_for_scoped_uids(self):
        repo = _fleet_repo()
        asked = []
        original = repo.get_latest_temperatures
        repo.get_latest_temperatures = lambda uids: asked.append(sorted(uids)) or original(uids)
        fleet.get_real_fleet(repo, scope=RtlScope(frozenset({2})))
        assert asked == [[2]]

    def test_an_empty_scope_reads_no_temperature_and_returns_no_rows(self):
        repo = _fleet_repo()
        result = fleet.get_real_fleet(repo, scope=RtlScope(frozenset()))
        assert result.status is fleet.FleetStatus.DATA and result.rows == ()
        assert "latest" not in repo.calls and result.summary.registered == 0

    def test_an_unregistered_assigned_uid_never_appears(self):
        result = fleet.get_real_fleet(_fleet_repo(), scope=RtlScope(frozenset({1, 9999})))
        assert [r.device_uid for r in result.rows] == [1]

    def test_unrestricted_is_the_whole_registered_fleet(self):
        assert len(fleet.get_real_fleet(_fleet_repo(), scope=UNRESTRICTED).rows) == 4
        assert len(fleet.get_real_fleet(_fleet_repo()).rows) == 4


# -------------------------------------------------------------------- Network
class TestNetworkScope:
    def test_rows_and_hierarchy_options_come_from_the_assigned_subset(self):
        repo = NetRepo(
            [1, 2, 3],
            mappings=[M(1, "TA1"), M(2, "TA2"), M(3, "TA3")],
            hierarchy=[_h(1, "TA1", zone="North"), _h(2, "TA2", zone="South"),
                       _h(3, "TA3", zone="East")],
        )
        result = net.get_current_network(repo, scope=RtlScope(frozenset({1, 3})))
        assert [r.device_uid for r in result.rows] == [1, 3]
        zones = set(net.cascade_options(list(result.rows), net.NetworkFilter())["zone"])
        assert zones == {"North", "East"}  # South belongs only to an RTL out of scope
        assert len(result.rows) == 2

    def test_an_unassigned_rtl_is_absent(self):
        repo = NetRepo([1, 2], mappings=[M(1, "TA1")], hierarchy=[])
        assert [r.device_uid for r in net.get_current_network(
            repo, scope=RtlScope(frozenset({1}))).rows] == [1]


# --------------------------------------------------------------------- Detail
class _Tripwire:
    def __getattr__(self, name):
        raise AssertionError(f"client source must not be read: {name}")


class TestDetailScope:
    def test_an_out_of_scope_uid_is_forbidden_before_any_source_read(self):
        scope = RtlScope(frozenset({1}))
        assert detail.get_rtl_detail(2, _Tripwire(), scope=scope).status is detail.DetailStatus.FORBIDDEN
        assert detail.get_temperature_history(2, "24h", _Tripwire(), scope=scope
                                              ).status is detail.HistoryStatus.FORBIDDEN

    def test_registered_unregistered_and_unassigned_are_indistinguishable(self):
        scope = RtlScope(frozenset())
        statuses = {detail.get_rtl_detail(u, _Tripwire(), scope=scope).status for u in (1, 2, 999999)}
        assert statuses == {detail.DetailStatus.FORBIDDEN}

    def test_a_denied_scope_is_forbidden_too(self):
        assert detail.get_rtl_detail(1, _Tripwire(), scope=DENIED).status is detail.DetailStatus.FORBIDDEN

    def test_callback_refuses_before_fetching(self):
        def boom(*a, **k):
            raise AssertionError("must not fetch")
        ctx = {"route": "rtl_detail", "rtl_uid": 2}
        body, c, h, e, _style = rtl_detail.populate(
            ctx, "24h", fetch_detail=boom, fetch_history=boom,
            scope_for=lambda: RtlScope(frozenset({1})))
        assert "forbidden" in repr(body).lower() or "access" in text_of(body).lower()
        assert c is None and h is None and e is None


# ---------------------------------------------------------------------- Events
class TestEventsScope:
    RANGE = (date(2026, 1, 1), date(2026, 12, 31))

    def _page(self, scope, registered=(1, 2, 3), repo=None, **kw):
        repo = repo or EventsRepo()
        return events.get_events_page(
            *self.RANGE, repository=repo,
            network_fetch=lambda **_: net.get_current_network(network_repo()),
            scope=scope, registered_fetch=lambda: set(registered), **kw), repo

    def test_only_events_of_assigned_uids_are_listed_and_counted(self):
        page, _ = self._page(RtlScope(frozenset({2})))
        assert {e.device_uid for e in page.events} == {2}
        assert page.total == sum(page.counts.values()) == 1  # its one 2026 event; the 2020 row is outside the window

    def test_an_unassigned_uid_filter_returns_nothing_for_a_technician(self):
        page, _ = self._page(RtlScope(frozenset({2})), uid_text="1")
        assert page.events == () and page.total == 0

    def test_historical_unregistered_uid_events_are_hidden_even_if_assigned(self):
        page, _ = self._page(RtlScope(frozenset({2, 77})), registered=(1, 2, 3))
        assert {e.device_uid for e in page.events} == {2}

    def test_type_and_date_filters_still_work_inside_the_scope(self):
        page, _ = self._page(RtlScope(frozenset({1, 2})), event_type="battery_low")
        assert {(e.event_type.value, e.device_uid) for e in page.events} == {("battery_low", 2)}

    def test_an_empty_scope_shows_no_events(self):
        page, repo = self._page(RtlScope(frozenset()))
        assert page.events == () and page.total == 0

    def test_a_denied_scope_shows_no_events(self):
        page, _ = self._page(DENIED)
        assert page.events == () and page.total == 0

    def test_unrestricted_is_unchanged(self):
        page, _ = self._page(UNRESTRICTED)
        assert page.total == 5 and 77 in {e.device_uid for e in page.events}

    def test_the_default_window_is_anchored_on_the_scopes_own_events(self):
        repo = EventsRepo()
        events.get_latest_event_time(repo, scope=RtlScope(frozenset({2})),
                                     registered_fetch=lambda: {1, 2, 3})
        assert repo.latest_uids == (2,)
        events.get_latest_event_time(repo, scope=UNRESTRICTED)
        assert repo.latest_uids is None

    def test_scope_is_part_of_the_sql_not_a_python_post_filter(self):
        clause = events_repo._scope_clause([3, 1, 2])
        assert clause == " AND device_uid IN (1,2,3)"
        assert events_repo._scope_clause([]) == " AND 1 = 0"  # empty is nothing, not "no filter"
        assert events_repo._scope_clause(None) == ""
        sql = events_repo._union(["high_temperature"], False, [5])
        assert "device_uid IN (5)" in sql
        assert "device_uid IN (5)" in events_repo._latest_sql([5])


# ------------------------------------------------------- callbacks use the scope
class TestCallbacksPassTheScope:
    def test_fleet_dashboard_network_and_events_receive_the_technician_scope(self):
        scope = RtlScope(frozenset({1}))
        seen = {}

        def rec(name):
            def fetch(*a, **k):
                seen[name] = k.get("scope")
                raise RuntimeError("stop")
            return fetch

        fleet_overview.populate({"route": "overview"}, fetch=rec("fleet"), scope_for=lambda: scope)
        rtl_dashboard.populate({"route": "rtl_dashboard"}, fetch=rec("dash"), scope_for=lambda: scope)
        rtl_network.load({"route": "rtl_network"}, fetch=rec("net"), scope_for=lambda: scope)
        historical_events.render({"route": "historical_events"}, "2026-01-01", "2026-02-01",
                                 "all", "", None, 0, fetch=rec("events"), scope_for=lambda: scope)
        assert seen == {"fleet": scope, "dash": scope, "net": scope, "events": scope}

    def test_dashboard_for_a_technician_is_factual_and_scoped(self):
        base = _fleet_repo()
        repo = NetRepo([1, 2, 3, 4], mappings=[M(1, "TA1"), M(2, "TA2")],
                       hierarchy=[_h(1, "TA1"), _h(2, "TA2")])
        repo.get_latest_temperatures = base.get_latest_temperatures
        d = dashboard.get_dashboard(
            fleet_fetch=lambda scope: fleet.get_real_fleet(repo, scope=scope),
            network_fetch=lambda scope: net.get_current_network(repo, scope=scope),
            scope=RtlScope(frozenset({1, 2})))
        assert d.fleet.registered == 2 and d.network.mapped == 2


# ------------------------------------------------------------- structural guard
SERVICES_MAY_READ_ASSIGNMENTS = {
    "services/rtl_scope.py",              # the one scope boundary
    "services/rtl_assignment_service.py",  # the Administrator workflow
    "services/rtl_assignment_bootstrap.py",  # the explicit one-time import
}
ASSIGNMENT_READS = re.compile(
    r"list_current_rtl_assignment_uids|list_current_rtl_assignments|rtl_technician_assignments"
    r"|get_current_rtl_assignment|list_rtl_assignment_history|list_rtl_assignment_uid_state"
)
REAL_ROUTE_MODULES = (
    "callbacks/fleet_overview.py", "callbacks/rtl_detail.py", "callbacks/rtl_network.py",
    "callbacks/historical_events.py", "callbacks/rtl_dashboard.py",
)


def _py(rel_dir):
    return sorted((ROOT / rel_dir).glob("*.py"))


class TestNoRouteBuildsItsOwnTechnicianFilter:
    """Future routes cannot quietly grow their own Technician UID filtering."""

    @pytest.mark.parametrize("folder", ["callbacks", "pages", "components", "services"])
    def test_only_the_scope_boundary_reads_assignments(self, folder):
        offenders = []
        for path in _py(folder):
            rel = path.relative_to(ROOT).as_posix()
            if rel in SERVICES_MAY_READ_ASSIGNMENTS or rel == "services/prototype_assignments.py":
                continue
            if ASSIGNMENT_READS.search(path.read_text(encoding="utf-8")):
                offenders.append(rel)
        assert offenders == [], (
            "only services/rtl_scope.py may turn assignments into a UID filter; "
            f"these read assignments themselves: {offenders}"
        )

    def test_the_assignment_workflow_is_only_reachable_from_its_own_callbacks(self):
        importers = []
        for folder in ("callbacks", "pages", "components"):
            for path in _py(folder):
                if "rtl_assignment_service" in path.read_text(encoding="utf-8"):
                    importers.append(path.relative_to(ROOT).as_posix())
        assert set(importers) <= {"callbacks/rtl_assignments.py", "components/rtl_assignments.py"}

    @pytest.mark.parametrize("rel", REAL_ROUTE_MODULES)
    def test_every_real_route_callback_takes_its_scope_from_the_shared_boundary(self, rel):
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert "current_rtl_scope" in source, rel
        assert "current_device_scope" not in source, f"{rel} still uses the synthetic scope"

    @pytest.mark.parametrize("rel", REAL_ROUTE_MODULES)
    def test_real_route_callbacks_do_not_compare_roles(self, rel):
        """Role semantics live in services.rtl_scope; a callback that branches
        on TECHNICIAN is a second, unaudited filter."""
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        assert not ({"TECHNICIAN", "ADMINISTRATOR", "GENERAL"} & names), rel

    def test_routing_checks_the_detail_scope_before_building_the_page(self):
        src = (ROOT / "callbacks/routing.py").read_text(encoding="utf-8")
        block = src[src.index('if route.name == "rtl_detail":'):][:2400]
        assert block.index("rtl_scope.allows(route.rtl_uid)") < block.index("rtl_detail.layout(")

    def test_services_default_to_unrestricted_only_where_a_caller_must_pass_scope(self):
        """Each real-data service takes an explicit scope keyword, and every
        real-route callback passes it."""
        for rel, needle in (
            ("callbacks/fleet_overview.py", "fetch(scope=scope)"),
            ("callbacks/rtl_network.py", "fetch(scope=scope)"),
            ("callbacks/rtl_dashboard.py", "fetch(scope=scope)"),
            ("callbacks/historical_events.py", "scope=scope"),
            ("callbacks/rtl_detail.py", "scope=scope"),
        ):
            assert needle in (ROOT / rel).read_text(encoding="utf-8"), rel
