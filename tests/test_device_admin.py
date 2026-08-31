"""Device Administration page — correctness of layout, rows and navigation.

Pins the contract that:
- the page renders with a searchable table
- devices appear through the approved data provider (hierarchy_service)
- clicking View navigates to the existing device dashboard (/devices/<id>)
- inactive records are rendered safely
- empty state / error state are handled
- no direct SQL import exists in the page module
- Manage action opens device management drawer
- View action still works correctly
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from callbacks.device_admin import (
    DEVICE_ADMIN_COLUMNS,
    build_device_admin_rows,
    device_row_target,
)
from components.needs_attention import needs_attention
from services.monitoring_service import (
    Freshness,
    FleetHealth,
    FreshnessRollup,
    aggregate_freshness,
    fleet_health_from_rows,
    severity_rank,
)
from tests.dash_tree import find_by_class, links, text_of

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
FRESH_TS = NOW - timedelta(minutes=10)
STALE_TS = NOW - timedelta(days=2)

F, S, N = Freshness.FRESH, Freshness.STALE, Freshness.NO_DATA


class _Device:
    def __init__(self, device_id, device_code, status, transformer_code, plant_name):
        self.device_id = device_id
        self.device_code = device_code
        self.status = status
        self.transformer_code = transformer_code
        self.plant_name = plant_name


def _row(plant, device, metric, ts):
    return type("R", (), {
        "plant_id": plant, "device_id": device,
        "metric": metric, "reading_ts": ts,
    })()


def _health(pairs):
    """FleetHealth from (plant, device, ts) triples, one metric each."""
    return fleet_health_from_rows(
        [_row(p, d, "temperature", ts) for p, d, ts in pairs], now=NOW
    )


class TestBuildDeviceAdminRows:
    def test_all_fresh_devices(self):
        health = _health([("p1", "d1", FRESH_TS), ("p1", "d2", FRESH_TS)])
        devices = [
            _Device("d1", "29017", "active", "aa12", "Itaipu"),
            _Device("d2", "29018", "active", "aa12", "Itaipu"),
        ]
        rows = build_device_admin_rows(devices, health)
        assert len(rows) == 2
        assert all(r["_state"] == "fresh" for r in rows)

    def test_stale_device_appears(self):
        health = _health([("p1", "d1", FRESH_TS), ("p1", "d2", STALE_TS)])
        devices = [
            _Device("d1", "29017", "active", "aa12", "Itaipu"),
            _Device("d2", "29018", "active", "aa12", "Itaipu"),
        ]
        rows = build_device_admin_rows(devices, health)
        stale_rows = [r for r in rows if r["_state"] == "stale"]
        assert len(stale_rows) == 1
        assert stale_rows[0]["device"] == "29018"

    def test_inactive_device_renders_safely(self):
        health = _health([("p1", "d1", FRESH_TS)])
        devices = [
            _Device("d1", "29017", "inactive", "aa12", "Itaipu"),
        ]
        rows = build_device_admin_rows(devices, health)
        assert rows[0]["status"] == "Inactive"
        assert rows[0]["_state"] == "fresh"

    def test_device_absent_from_health_is_no_data(self):
        health = _health([("p1", "d1", FRESH_TS)])
        devices = [
            _Device("d1", "29017", "active", "aa12", "Itaipu"),
            _Device("d9", "99999", "active", "aa13", "Ghost Plant"),
        ]
        rows = build_device_admin_rows(devices, health)
        ghost = [r for r in rows if r["device"] == "99999"][0]
        assert ghost["_state"] == "no_data"

    def test_row_carries_id_and_actions(self):
        """FIX-1C: the actions live in one column PER ACTION now, so a click
        can be attributed. View is not among them — the device name
        navigates, which is where View already went."""
        health = _health([("p1", "d1", FRESH_TS)])
        devices = [_Device("d1", "29017", "active", "aa12", "Itaipu")]
        rows = build_device_admin_rows(devices, health)
        assert rows[0]["id"] == "d1"
        assert rows[0]["assign"] == "[Assign](#)"
        assert rows[0]["manage"] == "[Manage](#)"
        assert "actions" not in rows[0], (
            "the shared cell that delivered one click to both drawers is gone"
        )

    def test_plant_and_transformer_labels_present(self):
        health = _health([("p1", "d1", FRESH_TS)])
        devices = [_Device("d1", "29017", "active", "aa12", "Itaipu")]
        rows = build_device_admin_rows(devices, health)
        assert rows[0]["plant"] == "Itaipu"
        assert rows[0]["transformer"] == "aa12"

    def test_each_action_cell_holds_exactly_one_link(self):
        """The invariant behind FIX-1C. Two links in one cell is precisely
        what `active_cell` cannot disambiguate, so a cell carrying more than
        one action is the defect returning."""
        health = _health([("p1", "d1", FRESH_TS)])
        devices = [_Device("d1", "29017", "active", "aa12", "Itaipu")]
        rows = build_device_admin_rows(devices, health)
        for column in ("assign", "manage"):
            assert rows[0][column].count("[") == 1, column


class TestDeviceRowTarget:
    def test_click_on_device_column_returns_href(self):
        active_cell = {"column_id": "device", "row_id": "d1"}
        target = device_row_target(active_cell)
        assert target == "/devices/d1"

    def test_click_on_non_device_column_returns_none(self):
        active_cell = {"column_id": "plant", "row_id": "d1"}
        assert device_row_target(active_cell) is None

    def test_none_active_cell_returns_none(self):
        assert device_row_target(None) is None

    def test_missing_row_id_returns_none(self):
        active_cell = {"column_id": "device", "row_id": None}
        assert device_row_target(active_cell) is None


class TestDeviceAdminColumns:
    def test_columns_match_layout_spec(self):
        """The page carries its own spec for the first paint and the callback
        replaces it on first fire, so the two must agree or the table
        reshuffles under the user.

        Compared against the rendered layout rather than a literal list: the
        literal version of this test passed while only restating the
        callback's spec back to itself, so a page that had drifted would not
        have failed it.
        """
        from dash import dash_table

        from pages.device_admin import layout
        from tests.dash_tree import walk

        table = next(
            n for n in walk(layout()) if isinstance(n, dash_table.DataTable)
        )
        assert table.columns == DEVICE_ADMIN_COLUMNS

    def test_device_is_link_column(self):
        assert any(c["id"] == "device" for c in DEVICE_ADMIN_COLUMNS)


class TestDeviceAdminPageLayout:
    def test_page_renders_with_toolbar(self):
        from pages.device_admin import layout
        page = layout()
        search = find_by_class(page, "device-admin-toolbar__search")
        assert len(search) == 1

    def test_page_has_entity_table(self):
        from pages.device_admin import layout
        page = layout()
        tables = [n for n in [page] if hasattr(n, "children")]
        # The page contains a table with id "device-admin-table"
        from tests.dash_tree import find_by_id
        table = find_by_id(page, "device-admin-table")
        assert table is not None

    def test_table_uses_shared_responsive_presentation(self):
        from pages.device_admin import layout
        page = layout()
        wrappers = find_by_class(page, "entity-table-wrapper--responsive")
        assert len(wrappers) == 1

    def test_table_distinguishes_administrative_and_freshness_axes(self):
        from pages.device_admin import layout
        page = layout()
        assert len(find_by_class(page, "entity-table-wrapper--administrative-axis")) == 1
        assert len(find_by_class(page, "entity-table-wrapper--freshness-axis")) == 1

    def test_register_button_exists(self):
        from pages.device_admin import layout
        page = layout()
        buttons = find_by_class(page, "device-admin-toolbar__register-btn")
        assert len(buttons) == 1

    def test_page_has_assign_drawer(self):
        from pages.device_admin import layout
        page = layout()
        from tests.dash_tree import find_by_id
        drawer = find_by_id(page, "assign-device-drawer")
        assert drawer is not None

    def test_page_has_manage_drawer(self):
        from pages.device_admin import layout
        page = layout()
        from tests.dash_tree import find_by_id
        drawer = find_by_id(page, "device-manage-drawer")
        assert drawer is not None


class TestNoSQLInPageModule:
    def test_page_module_has_no_sql_imports(self):
        import pages.device_admin as mod
        import inspect
        source = inspect.getsource(mod)
        assert "sql" not in source.lower() or "sql" not in source.split("from")[0].lower()
        # More precise: no raw SQL or repository imports
        for line in source.split("\n"):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert "text(" not in stripped, f"Raw SQL in page: {stripped}"
            assert "session.execute" not in stripped, f"Session in page: {stripped}"


class TestDeviceManageDrawerLayout:
    def test_drawer_returns_component(self):
        from components.device_manage_drawer import device_manage_drawer
        drawer = device_manage_drawer()
        assert hasattr(drawer, "children")

    def test_drawer_has_overlay(self):
        from components.device_manage_drawer import device_manage_drawer
        drawer = device_manage_drawer()
        from tests.dash_tree import find_by_id
        assert find_by_id(drawer, "manage-drawer-overlay") is not None

    def test_drawer_has_action_menu(self):
        from components.device_manage_drawer import device_manage_drawer
        drawer = device_manage_drawer()
        from tests.dash_tree import find_by_id
        assert find_by_id(drawer, "manage-action-menu") is not None

    def test_drawer_has_program_panel(self):
        from components.device_manage_drawer import device_manage_drawer
        drawer = device_manage_drawer()
        from tests.dash_tree import find_by_id
        assert find_by_id(drawer, "manage-program-panel") is not None

    def test_drawer_has_forwarding_panel(self):
        from components.device_manage_drawer import device_manage_drawer
        drawer = device_manage_drawer()
        from tests.dash_tree import find_by_id
        assert find_by_id(drawer, "manage-forwarding-panel") is not None

    def test_drawer_has_deactivate_panel(self):
        from components.device_manage_drawer import device_manage_drawer
        drawer = device_manage_drawer()
        from tests.dash_tree import find_by_id
        assert find_by_id(drawer, "manage-deactivate-panel") is not None

    def test_program_rtl_fields_present(self):
        from components.device_manage_drawer import device_manage_drawer
        drawer = device_manage_drawer()
        from tests.dash_tree import find_by_id
        assert find_by_id(drawer, "program-rtl-uid") is not None
        assert find_by_id(drawer, "program-rtl-transformer") is not None
        assert find_by_id(drawer, "program-rtl-msisdn") is not None

    def test_msisdn_field_is_enabled_for_manual_entry(self):
        """PROG-D1: no trustworthy Master MSISDN source exists, so the field
        is operator-entered — empty by default, never prefilled from
        devices.msisdn, bounded by the schema's 20-character limit."""
        from components.device_manage_drawer import device_manage_drawer
        drawer = device_manage_drawer()
        from tests.dash_tree import find_by_id
        msisdn = find_by_id(drawer, "program-rtl-msisdn")
        assert msisdn is not None
        assert getattr(msisdn, "disabled", False) is False
        assert not getattr(msisdn, "value", None)
        assert msisdn.maxLength == 20

    def test_program_button_records_a_request(self):
        """PROG-D7: the button must not imply anything is sent."""
        from components.device_manage_drawer import device_manage_drawer
        drawer = device_manage_drawer()
        from tests.dash_tree import find_by_id
        button = find_by_id(drawer, "program-rtl-confirm-btn")
        assert button is not None
        assert button.children == "Record Program Request"

    def test_has_no_prototype_language_left(self):
        """OPS-DEACT-1: all three drawer actions are persisted; no panel
        may describe itself as a prototype any more."""
        from components.device_manage_drawer import device_manage_drawer
        from tests.dash_tree import text_of
        drawer = device_manage_drawer()
        assert "prototype" not in text_of(drawer).lower()

    def test_deactivate_button_names_the_action_only(self):
        """DEACT-D7: no '(Prototype)' suffix and no transport implication."""
        from components.device_manage_drawer import device_manage_drawer
        from tests.dash_tree import find_by_id
        button = find_by_id(device_manage_drawer(), "deactivate-confirm-btn")
        assert button is not None
        assert button.children == "Deactivate RTL"
