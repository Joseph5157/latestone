"""My RTLs — a Technician's assignment work list on the Fleet Overview.

Pure tests only: the row builder, the sort, the rendering-condition function
and the presentation component, all exercised without a Dash callback or a
database. Wiring into `populate_overview` and the page layout is covered
separately in tests/test_my_rtls_wiring.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from callbacks.listings import (
    build_my_rtls_rows,
    my_rtls_section,
    sort_my_rtls_rows_exception_first,
)
from components.my_rtls import MY_RTLS_COLUMNS, my_rtls_panel
from repositories.plant_monitoring_repository import DevicePath
from services.device_scope import EMPTY, UNRESTRICTED, DeviceScope
from services.monitoring_service import Freshness, fleet_health_from_rows
from tests.dash_tree import find_by_exact_class, find_by_id, text_of

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
FRESH_TS = NOW - timedelta(minutes=10)
STALE_TS = NOW - timedelta(days=2)


def _row(device, ts, plant="p1", transformer="p1-t1", metric="temperature"):
    return type("R", (), {
        "plant_id": plant, "transformer_id": transformer,
        "device_id": device, "metric": metric, "reading_ts": ts,
    })()


def _health(triples):
    """FleetHealth from (device, ts) pairs, one metric each, all under p1/p1-t1."""
    return fleet_health_from_rows([_row(d, ts) for d, ts in triples], now=NOW)


def _path(device_id, plant_name="Plant One", transformer_code="T1", status="active"):
    return DevicePath(
        plant_id="p1", plant_name=plant_name, transformer_id="p1-t1",
        transformer_code=transformer_code, device_id=device_id,
        device_code=device_id.upper(), device_status=status,
    )


class TestRowsCoverEveryAssignedDevice:
    def test_every_scope_device_id_gets_a_row_even_absent_from_health(self, monkeypatch):
        """A Technician's assigned RTL that has never reported may have no
        FleetHealth rollup at all — it must still be listed (Known ambiguity
        in the gate), never silently dropped."""
        scope = DeviceScope(device_ids=frozenset({"d1", "d2"}))
        health = _health([("d1", FRESH_TS)])  # d2 has no rollup at all
        monkeypatch_list_device_paths(monkeypatch, [_path("d1"), _path("d2")])
        rows = build_my_rtls_rows(scope, health)
        assert {r["id"] for r in rows} == {"d1", "d2"}

    def test_missing_health_defaults_to_no_data(self, monkeypatch):
        scope = DeviceScope(device_ids=frozenset({"d1"}))
        health = _health([])
        monkeypatch_list_device_paths(monkeypatch, [_path("d1")])
        rows = build_my_rtls_rows(scope, health)
        assert rows[0]["_state"] == Freshness.NO_DATA.value
        assert "No data" in rows[0]["freshness"]

    def test_present_rollup_is_used_verbatim(self, monkeypatch):
        scope = DeviceScope(device_ids=frozenset({"d1"}))
        health = _health([("d1", FRESH_TS)])
        monkeypatch_list_device_paths(monkeypatch, [_path("d1")])
        rows = build_my_rtls_rows(scope, health)
        assert rows[0]["_state"] == Freshness.FRESH.value

    def test_freshness_label_counts_metrics_not_devices(self, monkeypatch):
        """A device's own rollup is over its metrics, matching
        build_device_rows — reusing the "devices" noun on a single RTL would
        misread as a fleet-level count."""
        scope = DeviceScope(device_ids=frozenset({"d1"}))
        health = fleet_health_from_rows(
            [_row("d1", FRESH_TS, metric="temperature"),
             _row("d1", None, metric="voltage")],
            now=NOW,
        )
        monkeypatch_list_device_paths(monkeypatch, [_path("d1")])
        rows = build_my_rtls_rows(scope, health)
        assert "metrics" in rows[0]["freshness"]

    def test_empty_scope_produces_no_rows(self, monkeypatch):
        calls = []
        monkeypatch_list_device_paths(monkeypatch, [], calls)
        rows = build_my_rtls_rows(EMPTY, _health([]))
        assert rows == []
        assert calls == [], "an EMPTY scope must not issue a label query"


class TestLabelsComeFromScopedListDevicePaths:
    def test_labels_use_the_scoped_batched_lookup(self, monkeypatch):
        scope = DeviceScope(device_ids=frozenset({"d1"}))
        health = _health([("d1", FRESH_TS)])
        seen = {}

        def fake(device_ids, *, scope):
            seen["ids"] = list(device_ids)
            seen["scope"] = scope
            return [_path("d1", plant_name="Itaipu", transformer_code="TX9")]

        monkeypatch.setattr(
            "callbacks.listings.hierarchy_service.list_device_paths", fake
        )
        rows = build_my_rtls_rows(scope, health)
        assert seen["ids"] == ["d1"]
        assert seen["scope"] is scope
        assert rows[0]["plant"] == "Itaipu"
        assert rows[0]["transformer"] == "TX9"
        assert rows[0]["device"] == "D1"

    def test_a_device_with_no_resolvable_label_falls_back_to_its_raw_id(
        self, monkeypatch
    ):
        """An id that matches nothing (e.g. a scope/query race) is shown as
        an identifier, never fabricated — the same convention
        build_exception_queue's `_code` fallback uses."""
        scope = DeviceScope(device_ids=frozenset({"ghost"}))
        health = _health([])
        monkeypatch_list_device_paths(monkeypatch, [])
        rows = build_my_rtls_rows(scope, health)
        assert rows[0]["device"] == "ghost"
        assert rows[0]["plant"] == ""
        assert rows[0]["transformer"] == ""

    def test_the_row_builder_never_uses_the_unscoped_fleet_wide_listing(self):
        """No hierarchy_code_index / list_all_devices — both are unscoped
        fleet-wide reads and would leak plant/transformer names outside the
        caller's own scope (ADR-004)."""
        import inspect

        from callbacks import listings

        source = inspect.getsource(listings.build_my_rtls_rows)
        assert "list_all_devices(" not in source
        assert "hierarchy_code_index(" not in source


class TestExceptionFirstOrdering:
    def test_no_data_sorts_above_stale_above_fresh(self, monkeypatch):
        scope = DeviceScope(device_ids=frozenset({"d_fresh", "d_stale", "d_none"}))
        health = _health([("d_fresh", FRESH_TS), ("d_stale", STALE_TS)])
        monkeypatch_list_device_paths(monkeypatch, [
            _path("d_fresh"), _path("d_stale"), _path("d_none"),
        ])
        rows = sort_my_rtls_rows_exception_first(build_my_rtls_rows(scope, health))
        assert [r["id"] for r in rows] == ["d_none", "d_stale", "d_fresh"]

    def test_ties_fall_back_to_device_code(self, monkeypatch):
        scope = DeviceScope(device_ids=frozenset({"d2", "d1"}))
        health = _health([("d1", FRESH_TS), ("d2", FRESH_TS)])
        monkeypatch_list_device_paths(monkeypatch, [_path("d1"), _path("d2")])
        rows = sort_my_rtls_rows_exception_first(build_my_rtls_rows(scope, health))
        assert [r["device"] for r in rows] == ["D1", "D2"]


class TestRenderingCondition:
    def test_unrestricted_scope_renders_nothing(self, monkeypatch):
        calls = []
        monkeypatch_list_device_paths(monkeypatch, [], calls)
        assert my_rtls_section(UNRESTRICTED, _health([])) is None
        assert calls == [], "an unrestricted render must issue zero label queries"

    def test_empty_scope_still_renders_a_panel(self, monkeypatch):
        calls = []
        monkeypatch_list_device_paths(monkeypatch, [], calls)
        block = my_rtls_section(EMPTY, _health([]))
        assert block is not None
        assert "No RTLs are currently assigned to you." in text_of(block)
        assert calls == [], "EMPTY has no ids, so no label query should run"

    def test_restricted_nonempty_scope_renders_the_table(self, monkeypatch):
        scope = DeviceScope(device_ids=frozenset({"d1"}))
        monkeypatch_list_device_paths(monkeypatch, [_path("d1")])
        block = my_rtls_section(scope, _health([("d1", FRESH_TS)]))
        assert find_by_id(block, "my-rtls-table") is not None


class TestMyRtlsPanelComponent:
    def test_columns_match_the_spec(self):
        assert [c["id"] for c in MY_RTLS_COLUMNS] == [
            "device", "plant", "transformer", "freshness",
        ]

    def test_empty_rows_render_a_truthful_empty_state_not_an_absent_panel(self):
        block = my_rtls_panel([])
        assert "No RTLs are currently assigned to you." in text_of(block)
        assert find_by_id(block, "my-rtls-table") is None

    def test_nonempty_rows_render_the_table_with_a_true_count(self):
        rows = [
            {"id": "d1", "device": "D1", "plant": "P", "transformer": "T",
             "freshness": "Fresh", "_severity": 0, "_state": "fresh"},
            {"id": "d2", "device": "D2", "plant": "P", "transformer": "T",
             "freshness": "Fresh", "_severity": 0, "_state": "fresh"},
        ]
        block = my_rtls_panel(rows)
        assert "2 assigned RTLs." in text_of(block)
        table = find_by_id(block, "my-rtls-table")
        assert table is not None
        assert table.data == rows

    def test_singular_count_wording(self):
        rows = [{"id": "d1", "device": "D1", "plant": "P", "transformer": "T",
                  "freshness": "Fresh", "_severity": 0, "_state": "fresh"}]
        assert "1 assigned RTL." in text_of(my_rtls_panel(rows))

    def test_no_action_controls_are_rendered(self):
        """ADR-016: this panel is read-only navigation, never a second entry
        point to Program RTL / Message Forwarding / Deactivate."""
        rows = [{"id": "d1", "device": "D1", "plant": "P", "transformer": "T",
                  "freshness": "Fresh", "_severity": 0, "_state": "fresh"}]
        rendered = text_of(my_rtls_panel(rows))
        for forbidden in ("Program RTL", "Message Forwarding", "Deactivate"):
            assert forbidden not in rendered

    def test_table_uses_the_shared_responsive_presentation(self):
        rows = [{"id": "d1", "device": "D1", "plant": "P", "transformer": "T",
                  "freshness": "Fresh", "_severity": 0, "_state": "fresh"}]
        wrappers = find_by_exact_class(my_rtls_panel(rows), "entity-table-wrapper")
        assert wrappers
        assert "entity-table-wrapper--responsive" in wrappers[0].className


def monkeypatch_list_device_paths(monkeypatch, paths, calls=None):
    """Stub `hierarchy_service.list_device_paths` as seen from callbacks.listings."""
    def fake(device_ids, *, scope):
        if calls is not None:
            calls.append(list(device_ids))
        return list(paths)

    monkeypatch.setattr(
        "callbacks.listings.hierarchy_service.list_device_paths", fake
    )
