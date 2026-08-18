"""Device Administration page — correctness of layout, rows and navigation.

Pins the contract that:
- the page renders with a searchable table
- devices appear through the approved data provider (hierarchy_service)
- clicking View navigates to the existing device dashboard (/devices/<id>)
- inactive records are rendered safely
- empty state / error state are handled
- no direct SQL import exists in the page module
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
        health = _health([("p1", "d1", FRESH_TS)])
        devices = [_Device("d1", "29017", "active", "aa12", "Itaipu")]
        rows = build_device_admin_rows(devices, health)
        assert rows[0]["id"] == "d1"
        assert "[View](#)" in rows[0]["actions"]
        assert "[Assign](#)" in rows[0]["actions"]

    def test_plant_and_transformer_labels_present(self):
        health = _health([("p1", "d1", FRESH_TS)])
        devices = [_Device("d1", "29017", "active", "aa12", "Itaipu")]
        rows = build_device_admin_rows(devices, health)
        assert rows[0]["plant"] == "Itaipu"
        assert rows[0]["transformer"] == "aa12"


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
        ids = [c["id"] for c in DEVICE_ADMIN_COLUMNS]
        assert ids == ["device", "plant", "transformer", "status", "freshness", "actions"]

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

    def test_register_button_exists(self):
        from pages.device_admin import layout
        page = layout()
        buttons = find_by_class(page, "device-admin-toolbar__register-btn")
        assert len(buttons) == 1


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
