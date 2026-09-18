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
        assert handler({"route": "overview"}) == (no_update,) * 6
        assert handler(None) == (no_update,) * 6

    def test_technician_direct_invocation_is_denied(self, monkeypatch):
        handler = self._handler(monkeypatch)
        with trusted_session(monkeypatch, user_id=104, role="technician"):
            workload, devices, columns, error, summary, empty = handler(
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
            workload, devices, _columns, error, _summary, _empty = handler(
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
            workload, _devices, columns, error, summary, _empty = handler(
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
