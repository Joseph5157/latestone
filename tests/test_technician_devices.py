"""Technician Devices page — the Technician's own operate-equipment surface.

ADR-016: a Technician's assigned devices, uncapped, with a "Manage" column
opening the SAME shared `device_manage_drawer()` the Administrator's
`/admin/devices` and every device dashboard already mount. No Assign
column, no Register button, no Status/Technician column — assignment is
never offered here (that boundary is ROUTE_POLICY/ADR-016, not this page).

Covers, in order: the page layout, the "every callback id exists in some
layout" contract for its own ids, the populate callback's P0-4 direct-
invocation guard (AUTH-HARDEN-1's lesson — page-context alone must never
gate a data read), row shape, and the two table-driven callbacks (row-click
navigation, the Manage-column drawer opener).
"""
from __future__ import annotations

import types

import pytest
from dash import Input, Output, State

from callbacks import technician_devices as cb
from pages import technician_devices as page
from repositories import plant_monitoring_repository as repo
from tests.auth_test_support import trusted_session
from tests.dash_tree import find_by_id, text_of


# ---------------------------------------------------------------------------
# Shared plumbing — same Capture pattern as tests/test_my_rtls_wiring.py
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


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------


class TestTechnicianDevicesLayout:
    def test_layout_carries_the_table_and_drawer(self):
        layout = page.layout()
        assert find_by_id(layout, page.TABLE_ID) is not None
        # device_manage_drawer() is mounted, unchanged, not a copy (ADR-016).
        from components.device_manage_drawer import MANAGE_DRAWER_ID
        assert find_by_id(layout, MANAGE_DRAWER_ID) is not None

    def test_layout_carries_no_assign_drawer(self):
        """Assignment is never offered here (ADR-016)."""
        layout = page.layout()
        assert find_by_id(layout, "assign-device-drawer") is None

    def test_columns_have_no_assign_status_or_technician_column(self):
        ids = {c["id"] for c in page.TECHNICIAN_DEVICE_COLUMNS}
        assert ids == {"device", "plant", "transformer", "freshness", "manage"}

    def test_page_heading_and_subtitle(self):
        rendered = text_of(page.layout())
        assert "Devices" in rendered
        assert "assigned to you" in rendered


# ---------------------------------------------------------------------------
# populate_technician_devices — the P0-4 direct-invocation guard
# ---------------------------------------------------------------------------


class TestPopulateTechnicianDevicesDirectInvocation:
    def _handler(self, monkeypatch, device_ids=frozenset()):
        from services import monitoring_service as svc

        monkeypatch.setattr(
            repo, "list_active_device_ids_for_user", lambda user_id: device_ids
        )
        monkeypatch.setattr(
            svc, "get_fleet_health",
            lambda *a, **k: types.SimpleNamespace(devices={}, device_last_updated={}),
        )
        monkeypatch.setattr(
            "services.hierarchy_service.list_device_paths",
            lambda ids, scope=None: [],
        )
        functions, _specs = _handlers()
        return functions["populate_technician_devices"]

    def test_a_route_mismatch_is_a_pure_noop(self, monkeypatch):
        from dash import no_update

        handler = self._handler(monkeypatch)
        result = handler({"route": "overview"})
        assert result == (no_update,) * 5
        result = handler(None)
        assert result == (no_update,) * 5

    def test_administrator_direct_invocation_is_denied(self, monkeypatch):
        """technician_devices is Technician-only (ADR-016) — unlike
        admin_devices, the Administrator does not get a pass here."""
        handler = self._handler(monkeypatch)
        with trusted_session(monkeypatch, user_id=1, role="administrator"):
            rows, columns, error, summary, empty = handler(
                {"route": "technician_devices"}
            )
        assert rows == []
        assert error is not None
        assert summary == ""
        assert columns == page.TECHNICIAN_DEVICE_COLUMNS

    def test_general_direct_invocation_is_denied(self, monkeypatch):
        handler = self._handler(monkeypatch)
        with trusted_session(monkeypatch, user_id=105, role="general"):
            rows, _columns, error, _summary, _empty = handler(
                {"route": "technician_devices"}
            )
        assert rows == []
        assert error is not None

    def test_technician_direct_invocation_succeeds(self, monkeypatch):
        handler = self._handler(monkeypatch)
        with trusted_session(monkeypatch, user_id=104, role="technician"):
            rows, columns, error, summary, empty = handler(
                {"route": "technician_devices"}
            )
        assert error is None
        assert rows == []  # no assignments in this fixture
        assert columns == page.TECHNICIAN_DEVICE_COLUMNS
        assert summary == "0 assigned RTLs."
        assert empty is not None  # truthful empty state, not a silent blank table

    def test_technician_with_assignments_gets_real_rows_and_no_empty_notice(
        self, monkeypatch
    ):
        handler = self._handler(monkeypatch, device_ids=frozenset({"plant-01-t1-d1"}))
        with trusted_session(monkeypatch, user_id=104, role="technician"):
            rows, _columns, error, summary, empty = handler(
                {"route": "technician_devices"}
            )
        assert error is None
        assert len(rows) == 1
        assert rows[0]["id"] == "plant-01-t1-d1"
        assert summary == "1 assigned RTL."
        assert empty is None

    def test_manage_column_carries_the_placeholder_link_on_every_row(self, monkeypatch):
        handler = self._handler(monkeypatch, device_ids=frozenset({"d1", "d2"}))
        with trusted_session(monkeypatch, user_id=104, role="technician"):
            rows, *_ = handler({"route": "technician_devices"})
        assert all(row["manage"] == cb._MANAGE_LINK for row in rows)


# ---------------------------------------------------------------------------
# Row-click navigation and the Manage-column drawer opener
# ---------------------------------------------------------------------------


class TestTechnicianDevicesTableWiring:
    def test_navigation_callback_is_wired_to_the_table(self):
        functions, specs = _handlers()
        args, kwargs = specs["navigate_from_technician_devices_table"]
        assert [(a.component_id, a.component_property) for a in args if isinstance(a, Input)] == [
            (page.TABLE_ID, "active_cell"),
        ]
        assert kwargs == {"prevent_initial_call": True}

    def test_a_non_device_column_click_does_not_navigate(self):
        from dash import no_update

        functions, _specs = _handlers()
        fn = functions["navigate_from_technician_devices_table"]
        assert fn({"column_id": "manage", "row_id": "d1"}) is no_update
        assert fn(None) is no_update

    def test_manage_opener_output_count_matches_the_shared_drawer(self):
        """Same 12-Output shape as callbacks.device_manage's two openers —
        ADR-016's "two openers, one drawer" becomes three."""
        functions, specs = _handlers()
        args, kwargs = specs["open_manage_drawer_from_technician_devices"]
        outputs = [a for a in args if isinstance(a, Output)]
        assert len(outputs) == 12
        assert kwargs == {"prevent_initial_call": True}

    def test_manage_opener_is_keyed_to_this_table_only(self):
        functions, specs = _handlers()
        args, _kwargs = specs["open_manage_drawer_from_technician_devices"]
        inputs = [(a.component_id, a.component_property) for a in args if isinstance(a, Input)]
        states = [(a.component_id, a.component_property) for a in args if isinstance(a, State)]
        assert inputs == [(page.TABLE_ID, "active_cell")]
        assert states == [(page.TABLE_ID, "data")]

    def test_a_click_on_a_non_manage_column_declines(self):
        from dash import no_update

        functions, _specs = _handlers()
        fn = functions["open_manage_drawer_from_technician_devices"]
        result = fn({"column_id": "device", "row_id": "d1"}, [{"id": "d1"}])
        assert result == (no_update,) * 12

    def test_a_manage_click_on_an_unknown_row_declines(self):
        from dash import no_update

        functions, _specs = _handlers()
        fn = functions["open_manage_drawer_from_technician_devices"]
        result = fn({"column_id": "manage", "row_id": "ghost"}, [{"id": "d1"}])
        assert result == (no_update,) * 12

    def test_a_manage_click_on_a_real_row_opens_the_drawer(self):
        functions, _specs = _handlers()
        fn = functions["open_manage_drawer_from_technician_devices"]
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


# ---------------------------------------------------------------------------
# VIEW_OWN_DEVICES capability
# ---------------------------------------------------------------------------


class TestViewOwnDevicesCapability:
    def test_only_the_technician_holds_it(self):
        from services.authorization import (
            ADMINISTRATOR, GENERAL, TECHNICIAN, VIEW_OWN_DEVICES,
            may_perform_capability,
        )
        assert may_perform_capability(TECHNICIAN, VIEW_OWN_DEVICES) is True
        assert may_perform_capability(ADMINISTRATOR, VIEW_OWN_DEVICES) is False
        assert may_perform_capability(GENERAL, VIEW_OWN_DEVICES) is False
