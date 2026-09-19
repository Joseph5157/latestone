"""Assignments page (ADMIN-ASSIGN-1) — technician workload roster plus the
shared per-device Assign/Manage table.

Covers: the pure row-building/sort functions, the page layout, the
populate callback's P0-4 direct-invocation guard (mirroring
`TestAdminDeviceListDirectInvocation` in tests/test_auth_harden.py), and
the three table-driven callbacks (row-click navigation, the Assign opener
reusing callbacks.device_assign's shared logic, the Manage opener mirroring
the Technician Devices page's own third opener).
"""
from __future__ import annotations

import types

import pytest
from dash import Input, Output, State

from callbacks import admin_assignments as cb
from callbacks.device_admin import UNASSIGNED
from pages import admin_assignments as page
from repositories import plant_monitoring_repository as repo
from services.admin_overview_service import AdminOverviewSummary
from tests.auth_test_support import trusted_session
from tests.dash_tree import find_by_id, text_of


# ---------------------------------------------------------------------------
# Shared plumbing — same Capture pattern as tests/test_technician_devices.py
# ---------------------------------------------------------------------------


class _Capture:
    def __init__(self):
        self.functions = {}
        self.specs = {}

    def callback(self, *args, **kwargs):
        def register(fn):
            self.functions[fn.__name__] = fn
            self.specs[fn.__name__] = (args, kwargs)
            return fn
        return register


def _handlers():
    capture = _Capture()
    cb.register(capture)
    return capture.functions, capture.specs


def _summary(**overrides):
    fields = dict(
        total_devices=10, assigned_devices=7, unassigned_devices=3,
        active_technicians=2, recently_registered_devices=0,
        unassigned_rows=(),
    )
    fields.update(overrides)
    return AdminOverviewSummary(**fields)


# ---------------------------------------------------------------------------
# build_technician_workload_rows — pure
# ---------------------------------------------------------------------------


class TestBuildTechnicianWorkloadRows:
    def test_counts_per_technician(self):
        technicians = [{"username": "a"}, {"username": "b"}]
        assignments = {"d1": "a", "d2": "a", "d3": "b"}
        rows = cb.build_technician_workload_rows(technicians, assignments)
        by_name = {r["technician"]: r["count"] for r in rows}
        assert by_name == {"a": 2, "b": 1}

    def test_most_loaded_first(self):
        technicians = [{"username": "light"}, {"username": "heavy"}]
        assignments = {"d1": "heavy", "d2": "heavy", "d3": "light"}
        rows = cb.build_technician_workload_rows(technicians, assignments)
        assert [r["technician"] for r in rows] == ["heavy", "light"]

    def test_a_technician_with_zero_assignments_still_gets_a_row(self):
        """The roster's whole purpose is workload visibility — an idle
        technician is exactly the fact this exists to surface."""
        technicians = [{"username": "idle"}, {"username": "busy"}]
        assignments = {"d1": "busy"}
        rows = cb.build_technician_workload_rows(technicians, assignments)
        by_name = {r["technician"]: r["count"] for r in rows}
        assert by_name == {"idle": 0, "busy": 1}

    def test_ties_break_alphabetically(self):
        technicians = [{"username": "zeta"}, {"username": "alpha"}]
        assignments = {"d1": "zeta", "d2": "alpha"}
        rows = cb.build_technician_workload_rows(technicians, assignments)
        assert [r["technician"] for r in rows] == ["alpha", "zeta"]

    def test_no_technicians_is_an_empty_roster_not_an_error(self):
        assert cb.build_technician_workload_rows([], {}) == []

    def test_an_assignment_for_an_unlisted_technician_is_not_counted(self):
        """An inactive/removed technician's stale assignment row must not
        fabricate a roster entry for someone no longer active."""
        technicians = [{"username": "active.tech"}]
        assignments = {"d1": "former.tech"}
        rows = cb.build_technician_workload_rows(technicians, assignments)
        assert rows == [{"id": "active.tech", "technician": "active.tech", "count": 0}]


# ---------------------------------------------------------------------------
# _device_sort_key — unassigned first, then by technician, then by device
# ---------------------------------------------------------------------------


class TestDeviceSortKey:
    def test_unassigned_sorts_before_any_assigned_row(self):
        unassigned = {"technician": "Unassigned", "device": "1"}
        assigned = {"technician": "a", "device": "0"}
        ordered = sorted([assigned, unassigned], key=cb._device_sort_key)
        assert ordered == [unassigned, assigned]

    def test_assigned_rows_group_by_technician_then_device(self):
        rows = [
            {"technician": "b", "device": "2"},
            {"technician": "a", "device": "2"},
            {"technician": "a", "device": "1"},
        ]
        ordered = sorted(rows, key=cb._device_sort_key)
        assert [(r["technician"], r["device"]) for r in ordered] == [
            ("a", "1"), ("a", "2"), ("b", "2"),
        ]


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------


class TestAdminAssignmentsLayout:
    def test_layout_carries_both_tables_and_both_drawers(self):
        layout = page.layout()
        assert find_by_id(layout, page.WORKLOAD_TABLE_ID) is not None
        assert find_by_id(layout, page.TABLE_ID) is not None
        from components.assign_device_drawer import ASSIGN_DRAWER_ID
        from components.device_manage_drawer import MANAGE_DRAWER_ID
        assert find_by_id(layout, ASSIGN_DRAWER_ID) is not None
        assert find_by_id(layout, MANAGE_DRAWER_ID) is not None

    def test_device_table_columns_match_device_admin_shape(self):
        """Deliberately duplicated (not imported) from
        callbacks.device_admin.DEVICE_ADMIN_COLUMNS — same rule
        pages/device_admin.py itself follows. Must never drift."""
        assert page.DEVICE_TABLE_COLUMNS == cb.DEVICE_TABLE_COLUMNS

    def test_page_heading(self):
        assert "Assignments" in text_of(page.layout())


# ---------------------------------------------------------------------------
# populate_admin_assignments — the P0-4 direct-invocation guard
# ---------------------------------------------------------------------------


class TestPopulateAdminAssignmentsDirectInvocation:
    def _handler(self, monkeypatch, technicians=(), assignments=None, devices=()):
        # `cb.get_technicians`/`cb.get_admin_overview` are direct
        # `from ... import` bindings inside callbacks/admin_assignments.py,
        # so each must be patched on `cb` itself — patching the origin
        # service module would not reach the already-bound local name.
        # `prototype_assignments`/`hierarchy_service`/`monitoring_service`
        # are imported as MODULES there, so patching their own attribute
        # (via `cb.<module>`) works instead.
        monkeypatch.setattr(cb, "get_technicians", lambda: list(technicians))
        monkeypatch.setattr(cb, "get_admin_overview", lambda *a, **k: _summary())
        monkeypatch.setattr(
            cb.prototype_assignments, "assigned_technicians",
            lambda: dict(assignments or {}),
        )
        monkeypatch.setattr(
            cb.hierarchy_service, "list_all_devices", lambda **k: list(devices)
        )
        monkeypatch.setattr(
            cb.monitoring_service, "get_fleet_health",
            lambda *a, **k: types.SimpleNamespace(devices={}, device_last_updated={}),
        )
        functions, _specs = _handlers()
        return functions["populate_admin_assignments"]

    def test_a_route_mismatch_is_a_pure_noop(self, monkeypatch):
        from dash import no_update

        handler = self._handler(monkeypatch)
        assert handler({"route": "overview"}) == (no_update,) * 7
        assert handler(None) == (no_update,) * 7

    def test_technician_direct_invocation_is_denied(self, monkeypatch):
        handler = self._handler(monkeypatch)
        with trusted_session(monkeypatch, user_id=104, role="technician"):
            workload, devices, columns, error, summary, empty, _line = handler(
                {"route": "admin_assignments"}
            )
        assert workload == []
        assert devices == []
        assert error is not None
        assert summary is None
        assert columns == cb.DEVICE_TABLE_COLUMNS

    def test_general_direct_invocation_is_denied(self, monkeypatch):
        handler = self._handler(monkeypatch)
        with trusted_session(monkeypatch, user_id=105, role="general"):
            workload, devices, _columns, error, _summary, _empty, _line = handler(
                {"route": "admin_assignments"}
            )
        assert workload == []
        assert devices == []
        assert error is not None

    def test_administrator_direct_invocation_succeeds(self, monkeypatch):
        handler = self._handler(
            monkeypatch,
            technicians=[{"username": "t.one"}],
            assignments={"d1": "t.one"},
        )
        with trusted_session(monkeypatch, user_id=1, role="administrator"):
            workload, _devices, columns, error, summary, _empty, _line = handler(
                {"route": "admin_assignments"}
            )
        assert error is None
        assert workload == [{"id": "t.one", "technician": "t.one", "count": 1}]
        assert columns == cb.DEVICE_TABLE_COLUMNS
        assert summary is not None


# ---------------------------------------------------------------------------
# Table-driven callbacks
# ---------------------------------------------------------------------------


class TestAdminAssignmentsTableWiring:
    def test_navigation_callback_is_wired_to_the_devices_table(self):
        _functions, specs = _handlers()
        args, kwargs = specs["navigate_from_assignment_devices_table"]
        assert [(a.component_id, a.component_property) for a in args if isinstance(a, Input)] == [
            (page.TABLE_ID, "active_cell"),
        ]
        assert kwargs == {"prevent_initial_call": True}

    def test_a_non_device_column_click_does_not_navigate(self):
        from dash import no_update

        functions, _specs = _handlers()
        fn = functions["navigate_from_assignment_devices_table"]
        assert fn({"column_id": "assign", "row_id": "d1"}) is no_update
        assert fn(None) is no_update

    def test_assign_opener_output_count_matches_the_shared_drawer(self):
        functions, specs = _handlers()
        args, kwargs = specs["open_assign_drawer_from_assignments"]
        outputs = [a for a in args if isinstance(a, Output)]
        assert len(outputs) == 11
        assert kwargs == {"prevent_initial_call": True}

    def test_assign_opener_is_keyed_to_this_table_only(self):
        _functions, specs = _handlers()
        args, _kwargs = specs["open_assign_drawer_from_assignments"]
        inputs = [(a.component_id, a.component_property) for a in args if isinstance(a, Input)]
        states = [(a.component_id, a.component_property) for a in args if isinstance(a, State)]
        assert inputs == [(page.TABLE_ID, "active_cell")]
        assert states == [(page.TABLE_ID, "data")]

    def test_assign_click_by_a_non_administrator_declines(self, monkeypatch):
        from dash import no_update

        functions, _specs = _handlers()
        fn = functions["open_assign_drawer_from_assignments"]
        with trusted_session(monkeypatch, user_id=104, role="technician"):
            result = fn({"column_id": "assign", "row_id": "d1"}, [{"id": "d1"}])
        assert result == (no_update,) * 11

    def test_assign_click_on_a_non_assign_column_declines(self, monkeypatch):
        from dash import no_update

        functions, _specs = _handlers()
        fn = functions["open_assign_drawer_from_assignments"]
        with trusted_session(monkeypatch, user_id=1, role="administrator"):
            result = fn({"column_id": "manage", "row_id": "d1"}, [{"id": "d1"}])
        assert result == (no_update,) * 11

    def test_manage_opener_output_count_matches_the_shared_drawer(self):
        functions, specs = _handlers()
        args, kwargs = specs["open_manage_drawer_from_assignments"]
        outputs = [a for a in args if isinstance(a, Output)]
        assert len(outputs) == 12
        assert kwargs == {"prevent_initial_call": True}

    def test_manage_click_on_a_real_row_opens_the_drawer(self):
        functions, _specs = _handlers()
        fn = functions["open_manage_drawer_from_assignments"]
        table_data = [{
            "id": "plant-01-t1-d1", "device": "29017",
            "transformer": "T04", "plant": "Three Gorges Dam",
        }]
        result = fn({"column_id": "manage", "row_id": "plant-01-t1-d1"}, table_data)
        style, device_id, action, device_code, transformer, plant = result[:6]
        assert style == {"display": "block"}
        assert device_id == "plant-01-t1-d1"
        assert action == "menu"
        assert device_code == "29017"
        assert transformer == "T04"
        assert plant == "Three Gorges Dam"

    def test_manage_click_on_an_unknown_row_declines(self):
        from dash import no_update

        functions, _specs = _handlers()
        fn = functions["open_manage_drawer_from_assignments"]
        result = fn({"column_id": "manage", "row_id": "ghost"}, [{"id": "d1"}])
        assert result == (no_update,) * 12


# ---------------------------------------------------------------------------
# ASSIGN-TOOLBAR-1 — the toolbar replaces the native filter row
# ---------------------------------------------------------------------------


def _row(device_id, plant_id, plant, technician, state="fresh"):
    return {
        "id": device_id, "device": device_id, "plant": plant, "transformer": "T1",
        "technician": technician, "_plant_id": plant_id, "_state": state,
    }


_ROWS = [
    _row("d1", "p1", "Three Gorges Dam", "Unassigned", "stale"),
    _row("d2", "p1", "Three Gorges Dam", "demo.tech01"),
    _row("d3", "p2", "Itaipu Dam", "demo.tech02"),
]


class TestAssignmentToolbarLayout:
    def test_the_rtl_table_has_no_native_filter_row(self):
        table = find_by_id(page.layout(), page.TABLE_ID)
        assert table.filter_action == "none"

    def test_the_toolbar_controls_are_on_the_page(self):
        layout = page.layout()
        for control_id in (
            page.SEARCH_ID, page.PLANT_FILTER_ID, page.DATA_FILTER_ID,
            page.TECHNICIAN_FILTER_ID, page.CLEAR_FILTERS_ID,
            page.DEVICE_SUMMARY_ID,
        ):
            assert find_by_id(layout, control_id) is not None, control_id

    def test_each_dropdown_is_labelled(self):
        layout = page.layout()
        for control_id, label in (
            (page.PLANT_FILTER_ID, "Plant"),
            (page.DATA_FILTER_ID, "Data"),
            (page.TECHNICIAN_FILTER_ID, "Technician"),
        ):
            assert text_of(find_by_id(layout, f"{control_id}-label")) == label


class TestAssignmentFiltering:
    def _devices(self, monkeypatch, **filters):
        monkeypatch.setattr(cb, "get_technicians", lambda: [])
        monkeypatch.setattr(cb, "get_admin_overview", lambda *a, **k: _summary())
        monkeypatch.setattr(cb.prototype_assignments, "assigned_technicians", dict)
        monkeypatch.setattr(cb.hierarchy_service, "list_all_devices", lambda **k: [])
        monkeypatch.setattr(
            cb.monitoring_service, "get_fleet_health",
            lambda *a, **k: types.SimpleNamespace(devices={}, device_last_updated={}),
        )
        monkeypatch.setattr(cb, "build_device_admin_rows", lambda *a, **k: list(_ROWS))
        functions, _specs = _handlers()
        with trusted_session(monkeypatch, user_id=1, role="administrator"):
            return functions["populate_admin_assignments"](
                {"route": "admin_assignments"}, **filters
            )

    def test_search_ignores_case(self, monkeypatch):
        """The native row matched case exactly: `three gorges` found nothing."""
        result = self._devices(monkeypatch, search="three gorges")
        assert [r["id"] for r in result[1]] == ["d1", "d2"]

    def test_filters_combine(self, monkeypatch):
        result = self._devices(monkeypatch, plant="p1", technician="demo.tech01")
        assert [r["id"] for r in result[1]] == ["d2"]

    def test_unassigned_filter(self, monkeypatch):
        result = self._devices(monkeypatch, technician=UNASSIGNED)
        assert [r["id"] for r in result[1]] == ["d1"]

    def test_data_filter(self, monkeypatch):
        result = self._devices(monkeypatch, freshness="stale")
        assert [r["id"] for r in result[1]] == ["d1"]

    def test_filters_leave_the_workload_and_cards_whole(self, monkeypatch):
        full = self._devices(monkeypatch)
        narrowed = self._devices(monkeypatch, search="itaipu")
        assert narrowed[0] == full[0]
        assert narrowed[4] is not None

    def test_summary_line_and_empty_state(self, monkeypatch):
        full = self._devices(monkeypatch)
        assert full[6] == "3 RTLs"
        assert full[5] is None
        none = self._devices(monkeypatch, search="no such rtl")
        assert none[1] == []
        assert none[6] == "Showing 0 of 3 RTLs"
        assert text_of(none[5]) == "No results"

    def test_populate_listens_to_every_filter(self):
        _functions, specs = _handlers()
        args, _kwargs = specs["populate_admin_assignments"]
        inputs = [(a.component_id, a.component_property) for a in args if isinstance(a, Input)]
        assert inputs == [
            ("page-context", "data"),
            (page.SEARCH_ID, "value"),
            (page.PLANT_FILTER_ID, "value"),
            (page.DATA_FILTER_ID, "value"),
            (page.TECHNICIAN_FILTER_ID, "value"),
        ]


class TestAssignmentFilterOptions:
    def test_options_are_refused_to_a_non_administrator(self, monkeypatch):
        functions, _specs = _handlers()
        fn = functions["load_assignment_filter_options"]
        with trusted_session(monkeypatch, user_id=104, role="technician"):
            plants, technicians = fn({"route": "admin_assignments"})
        assert plants == []
        assert [o["value"] for o in technicians] == ["all", UNASSIGNED]

    def test_options_for_an_administrator(self, monkeypatch):
        monkeypatch.setattr(
            cb.hierarchy_service, "list_plants",
            lambda **k: [types.SimpleNamespace(plant_id="p1", name="Itaipu Dam")],
        )
        monkeypatch.setattr(
            cb.prototype_assignments, "assigned_technicians", lambda: {"d1": "demo.tech01"},
        )
        functions, _specs = _handlers()
        fn = functions["load_assignment_filter_options"]
        with trusted_session(monkeypatch, user_id=1, role="administrator"):
            plants, technicians = fn({"route": "admin_assignments"})
        assert plants == [{"label": "Itaipu Dam", "value": "p1"}]
        assert [o["value"] for o in technicians] == ["all", UNASSIGNED, "demo.tech01"]

    def test_other_routes_are_a_noop(self):
        from dash import no_update

        functions, _specs = _handlers()
        assert functions["load_assignment_filter_options"]({"route": "x"}) == (
            no_update, no_update,
        )


class TestClearAssignmentFilters:
    def test_clear_resets_every_filter(self):
        functions, _specs = _handlers()
        assert functions["clear_assignment_filters"](1) == ("", None, "all", "all")

    def test_no_click_is_a_noop(self):
        from dash import no_update

        functions, _specs = _handlers()
        assert functions["clear_assignment_filters"](0) == (no_update,) * 4


def test_device_filter_summary():
    assert cb.device_filter_summary(120, 120) == "120 RTLs"
    assert cb.device_filter_summary(5, 120) == "Showing 5 of 120 RTLs"
