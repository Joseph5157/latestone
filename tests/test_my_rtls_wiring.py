"""My RTLs wiring — the slot, the callback Output, and the scope branch.

tests/test_my_rtls.py covers the row builder and component in isolation.
These tests cover how the panel reaches the page: its position in the
layout, its place in `populate_overview`'s Output list, and the guarantee
that EMPTY and UNRESTRICTED take genuinely different code paths rather than
being distinguished by truthiness of the same value.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from dash import Input, Output, State, no_update

from callbacks import listings
from pages import plants_overview
from services.device_scope import EMPTY, UNRESTRICTED, DeviceScope
from services.monitoring_service import fleet_health_from_rows
from tests.dash_tree import find_by_id, text_of, walk

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


class TestPageSlot:
    def test_layout_carries_the_my_rtls_slot(self):
        assert find_by_id(plants_overview.layout(), "my-rtls") is not None

    def test_slot_starts_empty(self):
        """Layout performs no queries; the panel can only exist after the
        listing callback has run — same contract as fleet-kpis/admin-summary."""
        slot = find_by_id(plants_overview.layout(), "my-rtls")
        assert not slot.children

    def test_slot_sits_below_fleet_condition(self):
        """FLEET-CONDITION-ORDER-1: Fleet Condition above My RTLs (client
        request), superseding TECH-WORKSPACE-1's original placement."""
        ids = [
            n.id for n in walk(plants_overview.layout())
            if getattr(n, "id", None) in {"my-rtls", "fleet-systemic-state"}
        ]
        assert ids == ["fleet-systemic-state", "my-rtls"]

    def test_slot_sits_above_needs_attention_too(self):
        ids = [
            n.id for n in walk(plants_overview.layout())
            if getattr(n, "id", None) in {"my-rtls", "needs-attention"}
        ]
        assert ids == ["my-rtls", "needs-attention"]


@pytest.fixture
def overview_callback():
    class Capture:
        def __init__(self):
            self.functions = {}
            self.specs = {}

        def callback(self, *args, **kwargs):
            def register(fn):
                self.functions[fn.__name__] = fn
                self.specs[fn.__name__] = (args, kwargs)
                return fn
            return register

    capture = Capture()
    listings.register(capture)
    return capture.functions["populate_overview"], capture.specs["populate_overview"]


@pytest.fixture
def my_rtls_nav_callback():
    """Same Capture pattern as `overview_callback`, for the row-click
    navigation callback instead — `navigate_from_my_rtls_table`."""
    class Capture:
        def __init__(self):
            self.functions = {}
            self.specs = {}

        def callback(self, *args, **kwargs):
            def register(fn):
                self.functions[fn.__name__] = fn
                self.specs[fn.__name__] = (args, kwargs)
                return fn
            return register

    capture = Capture()
    listings.register(capture)
    return (
        capture.functions["navigate_from_my_rtls_table"],
        capture.specs["navigate_from_my_rtls_table"],
    )


def _cell(column_id: str, row: int = 0, row_id: str | None = None) -> dict:
    """An `active_cell` as dash_table emits it."""
    return {"row": row, "column_id": column_id, "row_id": row_id}


class TestMyRtlsRowNavigation:
    """Row-click navigation for the My RTLs table — same contract every
    other listing table's navigate_from_* callback carries
    (tests/test_table_navigation.py): identity by row_id, never by viewport
    index, and this callback reuses `device_row_target` verbatim rather than
    a second definition of what a "device" cell means."""

    def test_the_callback_is_wired_to_the_my_rtls_table(self, my_rtls_nav_callback):
        _fn, (args, kwargs) = my_rtls_nav_callback
        assert [(a.component_id, a.component_property) for a in args if isinstance(a, Input)] == [
            ("my-rtls-table", "active_cell"),
        ]
        assert [(a.component_id, a.component_property) for a in args if isinstance(a, Output)] == [
            ("url", "pathname"),
        ]
        assert kwargs == {"prevent_initial_call": True}
        [output] = [a for a in args if isinstance(a, Output)]
        assert output.allow_duplicate is True

    def test_identity_column_click_navigates_to_the_correct_device(
        self, my_rtls_nav_callback
    ):
        fn, _spec = my_rtls_nav_callback
        target = fn(_cell(listings.DEVICE_LINK_COLUMN, row_id="plant-29-t2-d1"))
        assert target == "/devices/plant-29-t2-d1"

    def test_sorted_or_filtered_viewport_still_routes_by_row_id(
        self, my_rtls_nav_callback
    ):
        """`row` is the viewport index after sort/filter; the callback must
        follow `row_id` regardless of what `row` says."""
        fn, _spec = my_rtls_nav_callback
        target = fn(_cell(listings.DEVICE_LINK_COLUMN, row=17, row_id="plant-03-t3-d1"))
        assert target == "/devices/plant-03-t3-d1"

    def test_a_non_link_column_click_does_not_navigate(self, my_rtls_nav_callback):
        fn, _spec = my_rtls_nav_callback
        for column_id in ("plant", "transformer", "freshness"):
            assert fn(_cell(column_id, row_id="plant-29-t2-d1")) is no_update

    def test_no_active_cell_does_not_navigate(self, my_rtls_nav_callback):
        fn, _spec = my_rtls_nav_callback
        assert fn(None) is no_update

    def test_missing_row_id_does_not_navigate(self, my_rtls_nav_callback):
        fn, _spec = my_rtls_nav_callback
        assert fn(_cell(listings.DEVICE_LINK_COLUMN, row_id=None)) is no_update


class TestOutputCount:
    def test_the_output_list_carries_eleven_outputs_ending_in_my_rtls(
        self, overview_callback
    ):
        _fn, (args, _kwargs) = overview_callback
        outputs = [a for a in args if isinstance(a, Output)]
        assert len(outputs) == 11
        assert (outputs[-1].component_id, outputs[-1].component_property) == (
            "my-rtls", "children",
        )

    def test_inputs_and_state_are_unchanged(self, overview_callback):
        _fn, (args, kwargs) = overview_callback
        assert [(a.component_id, a.component_property) for a in args if isinstance(a, Input)] == [
            ("page-context", "data"),
        ]
        assert [(a.component_id, a.component_property) for a in args if isinstance(a, State)] == [
            ("auth-store", "data"),
        ]
        assert kwargs == {"prevent_initial_call": True}

    def test_other_routes_no_update_matches_the_output_count(self, overview_callback):
        fn, (args, _kwargs) = overview_callback
        outputs = [a for a in args if isinstance(a, Output)]
        assert fn({"route": "plant"}, None) == (no_update,) * len(outputs)


def _stub_common(monkeypatch, scope):
    """Everything populate_overview needs besides scope/my-rtls, held fixed."""
    plant = SimpleNamespace(
        plant_id="p1", name="Plant One", country="Chile",
        primary_fuel="Hydro", capacity_mw=100.0,
    )
    monkeypatch.setattr(listings.hierarchy_service, "list_plants", Mock(return_value=[plant]))
    monkeypatch.setattr(
        listings.hierarchy_service, "get_plant_hierarchy_counts",
        Mock(return_value={"p1": (1, 1)}),
    )
    monkeypatch.setattr(
        listings.monitoring_service, "get_fleet_health",
        Mock(return_value=fleet_health_from_rows([], now=NOW)),
    )
    monkeypatch.setattr(listings, "current_device_scope", lambda: scope)
    monkeypatch.setattr(listings, "administration_section", lambda *_: None)
    # `fleet_health_from_rows([])` leaves p1 with no rollup, which
    # `build_exception_queue` reports as NO_DATA and therefore fetches
    # display codes for — stubbed so this stays a "not db" test, same as
    # tests/test_fleet_condition.py's own callback fixture.
    monkeypatch.setattr(
        listings.hierarchy_service, "list_all_devices", Mock(return_value=[])
    )


class TestScopeBranchIsExplicitNotTruthiness:
    """EMPTY (frozenset()) and UNRESTRICTED (None) must take different code
    paths — a truthiness check on `scope.device_ids` would treat EMPTY the
    same as a falsy UNRESTRICTED-by-accident, which is exactly the bug
    class ADR-004 exists to prevent."""

    def test_unrestricted_renders_no_panel_and_issues_no_label_query(
        self, monkeypatch, overview_callback
    ):
        _stub_common(monkeypatch, UNRESTRICTED)
        calls = []
        monkeypatch.setattr(
            listings.hierarchy_service, "list_device_paths",
            lambda ids, *, scope: calls.append(list(ids)) or [],
        )
        fn, _spec = overview_callback
        result = fn({"route": "overview"}, None)
        assert result[-1] is None
        assert calls == []

    def test_empty_scope_renders_a_panel_and_issues_no_label_query(
        self, monkeypatch, overview_callback
    ):
        _stub_common(monkeypatch, EMPTY)
        calls = []
        monkeypatch.setattr(
            listings.hierarchy_service, "list_device_paths",
            lambda ids, *, scope: calls.append(list(ids)) or [],
        )
        fn, _spec = overview_callback
        result = fn({"route": "overview"}, None)
        assert result[-1] is not None
        assert "No RTLs are currently assigned to you." in text_of(result[-1])
        assert calls == []

    def test_restricted_nonempty_scope_renders_a_panel_and_issues_one_label_query(
        self, monkeypatch, overview_callback
    ):
        scope = DeviceScope(device_ids=frozenset({"plant-01-t1-d1"}))
        _stub_common(monkeypatch, scope)
        calls = []

        def fake_paths(ids, *, scope):
            calls.append(list(ids))
            return []

        monkeypatch.setattr(
            listings.hierarchy_service, "list_device_paths", fake_paths
        )
        fn, _spec = overview_callback
        result = fn({"route": "overview"}, None)
        assert result[-1] is not None
        assert len(calls) == 1
        assert calls[0] == ["plant-01-t1-d1"]


class TestSharedScopeAndFleetHealth:
    def test_my_rtls_reads_the_same_health_the_page_already_fetched(
        self, monkeypatch, overview_callback
    ):
        """No second freshness query for the panel — it must be built from
        the ONE get_fleet_health() call this render already makes."""
        scope = DeviceScope(device_ids=frozenset({"d1"}))
        _stub_common(monkeypatch, scope)
        health_calls = []
        real_get = listings.monitoring_service.get_fleet_health
        monkeypatch.setattr(
            listings.monitoring_service, "get_fleet_health",
            lambda *a, **k: (health_calls.append(1) or fleet_health_from_rows([], now=NOW)),
        )
        monkeypatch.setattr(
            listings.hierarchy_service, "list_device_paths",
            lambda ids, *, scope: [],
        )
        fn, _spec = overview_callback
        fn({"route": "overview"}, None)
        assert len(health_calls) == 1


class TestOtherRolesUnaffected:
    def test_admin_and_general_rendering_is_unaffected_by_the_new_slot(
        self, monkeypatch, overview_callback
    ):
        """Admin/General must render behaviorally unchanged: the plant
        table, KPI cards, Needs Attention and Administration outputs stay
        exactly what they already were; only the new slot changes (from
        no_update-shaped absence to an explicit None)."""
        _stub_common(monkeypatch, UNRESTRICTED)
        monkeypatch.setattr(
            listings.hierarchy_service, "list_device_paths",
            lambda ids, *, scope: [],
        )
        fn, _spec = overview_callback
        result = fn({"route": "overview"}, None)
        assert result[2] is None  # no error
        assert result[0], "plant rows still populate"
        assert result[-1] is None  # my-rtls slot: absent for UNRESTRICTED
