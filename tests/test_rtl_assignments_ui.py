"""ADR-032: Technician Assignments page, and the Technician's factual landing."""
from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pytest
from dash import no_update

from callbacks import rtl_assignments as cb
from callbacks import routing
from components import rtl_assignments as ui
from components import rtl_dashboard as dash_ui
from components.app_sidebar import sidebar_nav
from pages import plants_overview
from pages import rtl_assignments as page
from pages import rtl_dashboard as dash_page
from repositories.plant_monitoring_repository import RtlAssignmentRecord
from routes import RTL_ASSIGNMENTS_PATH, parse_pathname
from services import rtl_assignment_service as svc
from services.device_scope import UNRESTRICTED as DEVICE_UNRESTRICTED
from services.auth_service import AuthenticatedUser
from services.authorization import (
    ADMINISTRATOR, GENERAL, MANAGE_RTL_ASSIGNMENTS, TECHNICIAN,
    may_access_route, may_perform_capability, visible_nav_keys,
)
from services.rtl_dashboard_service import DashboardStatus, RTLDashboard
from services.rtl_fleet_service import FleetSummary
from services.rtl_network_service import NetworkSummary
from tests.dash_tree import find_by_class, text_of, walk
from tests.test_app_sidebar import links

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def admin():
    return AuthenticatedUser(user_id=1, username="a", full_name="A", role=ADMINISTRATOR)


def row(uid, tech=None, tech_id=None, assignment_id=None, legacy=False, codes=("TA1",)):
    return svc.AssignmentRow(uid, codes, assignment_id, tech_id, tech,
                             ("LEGACY_IMPORT" if legacy else "APPLICATION") if tech else None,
                             NOW if tech else None, legacy)


ROWS = (row(1, "Ann", 10, 100), row(2), row(3, "Bob", 11, 101, legacy=True, codes=()))
PAYLOAD = svc.to_payload(ROWS)


class TestRouteAndPolicy:
    def test_route_is_the_planned_address(self):
        assert RTL_ASSIGNMENTS_PATH == "/technicians/assignments"
        assert parse_pathname("/technicians/assignments").name == "rtl_assignments"
        assert parse_pathname("/technicians").name == "unknown"
        assert parse_pathname("/technicians/assignments/x").name == "unknown"

    def test_administrator_only(self):
        assert may_access_route(ADMINISTRATOR, "rtl_assignments")
        assert not may_access_route(TECHNICIAN, "rtl_assignments")
        assert not may_access_route(GENERAL, "rtl_assignments")
        assert may_perform_capability(ADMINISTRATOR, MANAGE_RTL_ASSIGNMENTS)
        assert not may_perform_capability(TECHNICIAN, MANAGE_RTL_ASSIGNMENTS)
        assert not may_perform_capability(GENERAL, MANAGE_RTL_ASSIGNMENTS)

    def test_navigation_offers_it_to_the_administrator_only(self):
        assert "assignments" in visible_nav_keys(ADMINISTRATOR)
        for role in (TECHNICIAN, GENERAL):
            assert "assignments" not in visible_nav_keys(role)
            assert "Technician Assignments" not in [l for l, _ in links(sidebar_nav(None, role))]
        hrefs = dict(links(sidebar_nav(None, ADMINISTRATOR)))
        assert hrefs["Technician Assignments"] == RTL_ASSIGNMENTS_PATH

    def test_routing_renders_the_page_for_the_route(self):
        assert 'route.name == "rtl_assignments"' in inspect.getsource(routing)


class TestLoad:
    def test_a_non_administrator_reads_nothing(self):
        def boom(**_):
            raise AssertionError("must not read")
        for role in (TECHNICIAN, GENERAL):
            who = AuthenticatedUser(user_id=2, username="t", full_name="T", role=role)
            payload, stats, error = cb.load({"route": "rtl_assignments"}, 0, fetch=boom,
                                            identity=lambda who=who: who)
            assert payload is None and stats is None and "Only an Administrator" in text_of(error)
        assert cb.load({"route": "rtl_assignments"}, 0, fetch=boom, identity=lambda: None)[0] is None

    def test_other_routes_are_ignored(self):
        assert cb.load({"route": "overview"}, 0) == (no_update,) * 3

    def test_an_administrator_gets_the_snapshot_and_counts(self):
        payload, stats, error = cb.load(
            {"route": "rtl_assignments"}, 0, identity=admin,
            fetch=lambda: svc.AssignmentOverview(True, ROWS))
        assert error is None and payload == PAYLOAD
        text = text_of(stats)
        assert "Registered RTLs" in text and "Unassigned RTLs" in text

    def test_an_unavailable_source_is_not_an_empty_list(self):
        payload, _s, error = cb.load({"route": "rtl_assignments"}, 0, identity=admin,
                                     fetch=lambda: svc.AssignmentOverview(False))
        assert payload is None and "unavailable" in text_of(error).lower()


class TestRenderAndFilters:
    def test_assigned_and_unassigned_pools(self):
        listing, _opts = cb.render(PAYLOAD, "unassigned", None, "")
        assert "Unassigned" in text_of(listing) and "Ann" not in text_of(listing)
        listing, opts = cb.render(PAYLOAD, "assigned", None, "")
        assert "Ann" in text_of(listing) and "Bob" in text_of(listing)
        assert {o["label"] for o in opts} == {"Ann", "Bob"}

    def test_technician_and_uid_filters(self):
        listing, _ = cb.render(PAYLOAD, "all", 11, "")
        assert "Bob" in text_of(listing) and "Ann" not in text_of(listing)
        listing, _ = cb.render(PAYLOAD, "all", None, "2")
        assert "Ann" not in text_of(listing)
        listing, _ = cb.render(PAYLOAD, "all", None, "999")
        assert "No RTLs match" in text_of(listing)

    def test_rows_show_uid_technician_transformer_and_since(self):
        text = text_of(ui.assignment_table(ROWS))
        assert "Ann" in text and "TA1" in text and "30 Sep 2026" in text
        assert "No current transformer mapping" in text

    def test_legacy_rows_do_not_show_a_fabricated_date(self):
        legacy_row = ROWS[2]
        assert ui.since_text(legacy_row) == "Imported from legacy assignment data"
        assert "2026" not in ui.since_text(legacy_row)

    def test_action_buttons_follow_the_row_state(self):
        labels = [b.children for b in walk(ui.assignment_table(ROWS)) if getattr(b, "n_clicks", None) == 0]
        assert labels.count("Assign") == 1 and labels.count("Reassign") == 2
        assert labels.count("History") == 3


class TestSelectAndPanel:
    def test_a_recreated_button_is_not_a_click(self):
        assert cb.select({"uid": 1, "mode": "assign"}, 0) is no_update
        assert cb.select({"uid": 1, "mode": "assign"}, None) is no_update
        assert cb.select(None, 1) is no_update
        assert cb.select({"uid": 1, "type": "x", "mode": "assign"}, 1) == {"uid": 1, "mode": "assign"}

    def _panel(self, selected, **kw):
        return cb.open_panel(selected, PAYLOAD, identity=admin,
                             technicians=lambda: [(10, "Ann"), (11, "Bob"), (12, "Cy")],
                             history=lambda uid: [], **kw)

    def test_assign_offers_every_technician(self):
        style, title, note, options, value, _h, _m = self._panel({"uid": 2, "mode": "assign"})
        assert style == page.VISIBLE_STYLE and "Assign RTL 2" in title and value is None
        assert [o["label"] for o in options] == ["Ann", "Bob", "Cy"]

    def test_reassign_excludes_the_current_technician_and_says_history_is_kept(self):
        _s, title, note, options, _v, _h, _m = self._panel({"uid": 1, "mode": "reassign"})
        assert "Reassign RTL 1" in title and "Ann" in note and "history" in note
        assert [o["label"] for o in options] == ["Bob", "Cy"]

    def test_history_mode_has_no_target_picker(self):
        style, title, _n, options, _v, history, _m = self._panel({"uid": 1, "mode": "history"})
        assert "History for RTL 1" in title and options == [] and history is not None

    def test_nothing_opens_for_a_non_administrator(self):
        out = cb.open_panel({"uid": 1, "mode": "assign"}, PAYLOAD, identity=lambda: None)
        assert out[0] == page.HIDDEN_STYLE

    def test_history_table_wording(self):
        base = dict(device_uid=1, technician_user_id=10, technician_username="ann",
                    imported_at=NOW, ended_at=None, ended_by=None)
        legacy = RtlAssignmentRecord(assignment_id=1, technician_name="Ann", provenance="LEGACY_IMPORT",
                                     assigned_at=None, assigned_by=None, assigned_by_name=None, **base)
        app = RtlAssignmentRecord(assignment_id=2, technician_name="Bob", provenance="APPLICATION",
                                  assigned_at=NOW, assigned_by=1, assigned_by_name="Root",
                                  **{**base, "technician_user_id": 11, "ended_at": NOW, "ended_by": 1})
        text = text_of(ui.history_table([legacy, app]))
        assert "Imported from legacy assignment data" in text and "Root" in text and "Current" in text
        assert "LEGACY_IMPORT" not in text and "APPLICATION" not in text
        assert "never been assigned" in text_of(ui.history_table([]))


class TestConfirm:
    SEL = {"uid": 2, "mode": "assign"}

    def test_it_needs_a_target(self):
        msg, version = cb.confirm(self.SEL, PAYLOAD, None, 3, identity=admin)
        assert "Choose a Technician" in msg and version is no_update

    def test_assign_calls_the_service_as_the_current_identity(self):
        seen = {}
        msg, version = cb.confirm(self.SEL, PAYLOAD, 10, 3, identity=admin,
                                  assign=lambda uid, tech, actor: seen.update(uid=uid, tech=tech, actor=actor))
        assert (seen["uid"], seen["tech"]) == (2, 10)
        assert seen["actor"].role == ADMINISTRATOR
        assert "assigned" in msg and version == 4

    def test_reassign_carries_the_assignment_the_operator_saw(self):
        seen = {}
        cb.confirm({"uid": 1, "mode": "reassign"}, PAYLOAD, 11, 0, identity=admin,
                   reassign=lambda uid, tech, expected_assignment_id, actor: seen.update(
                       uid=uid, tech=tech, expected=expected_assignment_id))
        assert seen == {"uid": 1, "tech": 11, "expected": 100}

    def test_a_refusal_is_shown_and_the_list_reloads(self):
        def refuse(uid, tech, actor):
            raise svc.AlreadyAssigned("That RTL is already assigned.")
        msg, version = cb.confirm(self.SEL, PAYLOAD, 10, 3, identity=admin, assign=refuse)
        assert msg == "That RTL is already assigned." and version == 4

    def test_an_unexpected_failure_shows_no_internals(self):
        def boom(uid, tech, actor):
            raise RuntimeError("password=hunter2")
        msg, version = cb.confirm(self.SEL, PAYLOAD, 10, 3, identity=admin, assign=boom)
        assert "hunter2" not in msg and version is no_update

    def test_history_mode_confirms_nothing(self):
        assert cb.confirm({"uid": 1, "mode": "history"}, PAYLOAD, 10, 0, identity=admin) == (no_update,) * 2


class TestClientWordingOnly:
    def test_no_sql_table_names_or_enum_values_reach_the_page(self):
        rendered = " ".join(text_of(x) for x in (
            page.layout(), ui.stats(ROWS), ui.assignment_table(ROWS), ui.unavailable_panel()))
        for banned in ("techmician", "technician_assignments", "device_list", "persons",
                       "LEGACY_IMPORT", "APPLICATION", "dbo."):
            assert banned not in rendered
        assert "Unassigned RTLs" in rendered


# ------------------------------------------------------ Technician landing/lists
def dashboard(registered=3):
    return RTLDashboard(
        DashboardStatus.DATA,
        fleet=FleetSummary(registered, 2, 2, registered - 2, 0, 0),
        network=_net(registered),
        latest_reading=datetime(2026, 9, 1, 8, 0), by_zone=(("North", 2),))


def _net(n):
    fields = {name: 0 for name in NetworkSummary.__dataclass_fields__}
    fields.update({k: v for k, v in (("registered", n), ("mapped", 2)) if k in fields})
    return NetworkSummary(**fields)


class TestTechnicianLanding:
    def test_counts_and_links_are_factual(self):
        text = text_of(dash_ui.dashboard_body(dashboard(), assigned_only=True))
        for wanted in ("Assigned RTLs", "Temperature data available", "No temperature data",
                       "View Assigned RTLs", "View Network", "View Historical Events"):
            assert wanted in text
        hrefs = [getattr(n, "href", None) for n in walk(dash_ui.dashboard_body(dashboard(), assigned_only=True))]
        assert "/rtls" in hrefs and "/rtls/network" in hrefs and "/events" in hrefs

    def test_no_synthetic_or_unsupported_concepts(self):
        text = text_of(dash_ui.dashboard_body(dashboard(), assigned_only=True)).lower()
        for banned in ("plant", "online", "offline", "needs attention", "voltage", "current (a)",
                       "active power", "gauge", "registered rtls"):
            assert banned not in text

    def test_no_assignment_management_controls(self):
        body = dash_ui.dashboard_body(dashboard(), assigned_only=True)
        assert "assign" not in " ".join(str(getattr(n, "href", "")) for n in walk(body)).lower()
        assert "Technician Assignments" not in text_of(body)

    def test_an_empty_assignment_set_says_so_instead_of_showing_zeros(self):
        text = text_of(dash_ui.dashboard_body(dashboard(0), assigned_only=True))
        assert "No RTLs are assigned to you yet" in text

    def test_administrator_dashboard_is_unchanged(self):
        text = text_of(dash_ui.dashboard_body(dashboard()))
        assert "Registered RTLs" in text and "Assigned RTLs" not in text

    def test_layout_titles(self):
        assert "assigned to you" in text_of(dash_page.layout(assigned_only=True)).lower()
        assert "Assigned RTLs" in text_of(plants_overview.layout(assigned_only=True))
        assert "Registered RTLs" in text_of(plants_overview.layout())

    def test_technician_navigation_is_factual(self):
        labels = [l for l, _ in links(sidebar_nav(None, TECHNICIAN))]
        assert labels[:4] == ["Assigned RTLs", "Network", "Historical Events", "Dashboard"]
        assert "Devices" not in labels and "Command Center" not in labels
        assert "Technician Assignments" not in labels


class TestLegacyCommandCenterUnreachable:
    def test_routing_never_renders_the_synthetic_command_center_for_a_permitted_scope(self, monkeypatch):
        from services.rtl_scope import RtlScope
        handler = _handler(routing, "route_to_page")
        for role in (ADMINISTRATOR, TECHNICIAN):
            user = AuthenticatedUser(user_id=1, username="u", full_name="U", role=role)
            monkeypatch.setattr(routing, "current_identity", lambda user=user: user)
            monkeypatch.setattr(routing, "current_device_scope", lambda: DEVICE_UNRESTRICTED)
            scope = RtlScope(None) if role == ADMINISTRATOR else RtlScope(frozenset({1}))
            monkeypatch.setattr(routing, "current_rtl_scope", lambda scope=scope: scope)
            for path in ("/", "/command-center"):
                _layout, ctx = handler(path, "", {})
                assert ctx == {"route": "rtl_dashboard"}, (role, path)


def _handler(module, name):
    captured = {}

    class App:
        def callback(self, *a, **k):
            def deco(fn):
                captured[fn.__name__] = fn
                return fn
            return deco
    module.register(App())
    return captured[name]


class TestAssignedListWording:
    def test_a_technicians_list_says_assigned_not_registered(self):
        from components import rtl_fleet
        from callbacks import fleet_overview

        summary = FleetSummary(2, 1, 1, 1, 0, 0)
        assigned = text_of(rtl_fleet.summary_block(summary, True))
        assert "Assigned RTLs" in assigned and "assigned RTLs have a" in assigned
        assert "Registered RTLs" not in assigned and "Client RTL directory" not in assigned
        assert "Registered RTLs" in text_of(rtl_fleet.summary_block(summary))
        assert "is_assigned_only(scope)" in inspect.getsource(fleet_overview)
