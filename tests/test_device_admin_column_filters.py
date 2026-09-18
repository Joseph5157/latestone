"""DEVICE-FILTERS-1 — per-column filters on Device Management.

The toolbar gains Plant, Transformer, Data, Technician and Last reading
filters beside Search and Status, plus Clear filters. All pure logic here:
no Dash runtime, no database.
"""
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest

import app as app_module
from callbacks import device_admin
from callbacks.device_admin import (
    filter_device_rows,
    last_reading_band,
    plant_filter_options,
    technician_filter_options,
    transformer_filter_options,
)
from pages import device_admin as page
from tests.dash_tree import find_by_id


def row(device, plant_id, plant, transformer_id, transformer, *, status="Active",
        state="fresh", technician="Unassigned", band="lt1h"):
    return {
        "id": f"{transformer_id}-{device}",
        "device": device,
        "plant": plant,
        "transformer": transformer,
        "status": status,
        "freshness": state.capitalize(),
        "technician": technician,
        "_plant_id": plant_id,
        "_transformer_id": transformer_id,
        "_state": state,
        "_reading_band": band,
    }


ROWS = [
    row("29001", "p1", "Alpha", "p1-t1", "aa01", technician="demo.tech01"),
    row("29002", "p1", "Alpha", "p1-t2", "aa02", state="stale", band="gt24h"),
    row("29003", "p2", "Beta", "p2-t1", "bb01", state="no_data", band="none",
        technician="demo.tech02"),
    row("29004", "p2", "Beta", "p2-t1", "bb01", status="Inactive", state="stale",
        band="1to24h", technician="demo.tech01"),
]


def devices(rows):
    return [r["device"] for r in rows]


class TestLastReadingBand:
    @pytest.mark.parametrize("age, band", [
        (None, "none"),
        (timedelta(minutes=0), "lt1h"),
        (timedelta(minutes=59, seconds=59), "lt1h"),
        (timedelta(hours=1), "1to24h"),
        (timedelta(hours=24), "1to24h"),
        (timedelta(hours=24, seconds=1), "gt24h"),
        (timedelta(days=9), "gt24h"),
    ])
    def test_bands(self, age, band):
        assert last_reading_band(age) == band

    def test_rows_carry_the_band_and_ids(self):
        now = device_admin.monitoring_service._now()
        d = SimpleNamespace(
            device_id="p1-t1-d1", device_code="29001", status="active",
            transformer_id="p1-t1", transformer_code="aa01",
            plant_id="p1", plant_name="Alpha",
        )
        health = SimpleNamespace(
            devices={}, device_last_updated={"p1-t1-d1": now - timedelta(hours=3)}
        )
        [r] = device_admin.build_device_admin_rows([d], health, {}, now=now)
        assert r["_plant_id"] == "p1"
        assert r["_transformer_id"] == "p1-t1"
        assert r["_reading_band"] == "1to24h"


class TestColumnFilters:
    def test_no_new_filter_changes_nothing(self):
        assert filter_device_rows(ROWS, "", "all") == ROWS
        assert filter_device_rows(
            ROWS, "", "all", plant=None, transformer=None,
            freshness="all", technician="all", reading="all",
        ) == ROWS

    def test_plant(self):
        assert devices(filter_device_rows(ROWS, "", "all", plant="p2")) == ["29003", "29004"]

    def test_transformer(self):
        assert devices(filter_device_rows(ROWS, "", "all", plant="p1", transformer="p1-t2")) == ["29002"]

    def test_transformer_left_over_from_another_plant_is_ignored(self):
        """Changing Plant clears Transformer in the browser, but the table can
        render once with the old value first. It must not flash empty."""
        assert devices(
            filter_device_rows(ROWS, "", "all", plant="p2", transformer="p1-t2")
        ) == ["29003", "29004"]

    @pytest.mark.parametrize("state, expected", [
        ("fresh", ["29001"]),
        ("stale", ["29002", "29004"]),
        ("no_data", ["29003"]),
    ])
    def test_data(self, state, expected):
        assert devices(filter_device_rows(ROWS, "", "all", freshness=state)) == expected

    def test_technician(self):
        assert devices(filter_device_rows(ROWS, "", "all", technician="demo.tech01")) == ["29001", "29004"]

    def test_unassigned(self):
        assert devices(filter_device_rows(ROWS, "", "all", technician="_unassigned")) == ["29002"]

    @pytest.mark.parametrize("band, expected", [
        ("lt1h", ["29001"]),
        ("1to24h", ["29004"]),
        ("gt24h", ["29002"]),
        ("none", ["29003"]),
    ])
    def test_last_reading(self, band, expected):
        assert devices(filter_device_rows(ROWS, "", "all", reading=band)) == expected

    def test_filters_combine(self):
        assert devices(filter_device_rows(
            ROWS, "290", "active", plant="p2", freshness="no_data",
            technician="demo.tech02", reading="none",
        )) == ["29003"]


class TestOptions:
    def test_plant_options_are_every_plant_by_name(self):
        plants = [SimpleNamespace(plant_id="p2", name="Beta"),
                  SimpleNamespace(plant_id="p1", name="Alpha")]
        assert plant_filter_options(plants) == [
            {"label": "Alpha", "value": "p1"},
            {"label": "Beta", "value": "p2"},
        ]

    def test_transformer_options_by_code(self):
        transformers = [SimpleNamespace(transformer_id="p1-t2", transformer_code="aa02"),
                        SimpleNamespace(transformer_id="p1-t1", transformer_code="aa01")]
        assert transformer_filter_options(transformers) == [
            {"label": "aa01", "value": "p1-t1"},
            {"label": "aa02", "value": "p1-t2"},
        ]

    def test_technician_options_lead_with_all_and_unassigned(self):
        options = technician_filter_options({"d1": "demo.tech02", "d2": "demo.tech01", "d3": "demo.tech02"})
        assert options == [
            {"label": "All", "value": "all"},
            {"label": "Unassigned", "value": "_unassigned"},
            {"label": "demo.tech01", "value": "demo.tech01"},
            {"label": "demo.tech02", "value": "demo.tech02"},
        ]


class TestLayout:
    def test_every_filter_is_on_the_page(self):
        lay = page.layout()
        for control_id in (
            "device-admin-search", "device-admin-status-filter",
            "device-admin-plant-filter", "device-admin-transformer-filter",
            "device-admin-data-filter", "device-admin-technician-filter",
            "device-admin-reading-filter", "device-admin-clear-filters",
        ):
            assert find_by_id(lay, control_id) is not None, control_id

    def test_transformer_waits_for_a_plant(self):
        assert find_by_id(page.layout(), "device-admin-transformer-filter").disabled is True

    def test_data_options_are_the_freshness_states(self):
        options = find_by_id(page.layout(), "device-admin-data-filter").options
        assert [o["value"] for o in options] == ["all", "fresh", "stale", "no_data"]
        assert [o["label"] for o in options] == ["All", "Fresh", "Stale", "No data"]

    def test_reading_options_are_the_bands(self):
        options = find_by_id(page.layout(), "device-admin-reading-filter").options
        assert [o["value"] for o in options] == ["all", "lt1h", "1to24h", "gt24h", "none"]

    @pytest.mark.parametrize("control_id", [
        "device-admin-plant-filter", "device-admin-transformer-filter",
        "device-admin-data-filter", "device-admin-technician-filter",
        "device-admin-reading-filter",
    ])
    def test_each_dropdown_is_named_by_a_group_label(self, control_id):
        from tests.dash_tree import walk

        lay = page.layout()
        group = next(
            n for n in walk(lay)
            if getattr(n, "role", None) == "group"
            and any(getattr(c, "id", None) == control_id for c in (
                n.children if isinstance(n.children, list) else [n.children]))
        )
        label = find_by_id(lay, getattr(group, "aria-labelledby"))
        assert label is not None and label.children


class TestWiring:
    def _callback(self, output):
        return next(c for c in app_module.app._callback_list if output in c["output"])

    def test_populate_reads_every_filter(self):
        populate = self._callback("device-admin-table.data")
        assert {(i["id"], i["property"]) for i in populate["inputs"]} == {
            ("page-context", "data"),
            ("device-admin-search", "value"),
            ("device-admin-status-filter", "value"),
            ("device-admin-plant-filter", "value"),
            ("device-admin-transformer-filter", "value"),
            ("device-admin-data-filter", "value"),
            ("device-admin-technician-filter", "value"),
            ("device-admin-reading-filter", "value"),
        }

    def test_option_loaders_check_the_capability(self):
        import inspect

        app = _CapturingApp()
        device_admin.register(app)
        for name in ("_load_filter_options", "_load_transformer_options"):
            assert "require_capability" in inspect.getsource(app.functions[name])

    def test_changing_plant_resets_transformer(self, monkeypatch):
        monkeypatch.setattr(device_admin, "current_identity", lambda: SimpleNamespace(user_id=1))
        monkeypatch.setattr(device_admin, "require_capability", lambda *a, **k: None)
        monkeypatch.setattr(
            device_admin.hierarchy_service, "list_transformers",
            lambda plant_id, scope: [SimpleNamespace(transformer_id="p1-t1", transformer_code="aa01")],
        )
        app = _CapturingApp()
        device_admin.register(app)
        options, disabled, value = app.functions["_load_transformer_options"]("p1")
        assert options == [{"label": "aa01", "value": "p1-t1"}]
        assert disabled is False
        assert value is None
        assert app.functions["_load_transformer_options"](None) == ([], True, None)

    def test_clear_filters_resets_everything(self):
        app = _CapturingApp()
        device_admin.register(app)
        assert app.functions["_clear_filters"](1) == ("", "all", None, "all", "all", "all")

    def test_populate_applies_the_new_filters(self, monkeypatch):
        monkeypatch.setattr(device_admin, "current_identity", lambda: SimpleNamespace(user_id=1))
        monkeypatch.setattr(device_admin, "require_capability", lambda *a, **k: None)
        monkeypatch.setattr(device_admin.hierarchy_service, "list_all_devices",
                            lambda include_inactive=False: [
                                SimpleNamespace(status=r["status"].lower()) for r in ROWS
                            ])
        monkeypatch.setattr(device_admin.monitoring_service, "get_fleet_health",
                            lambda *a, **k: None)
        monkeypatch.setattr(device_admin.prototype_assignments, "assigned_technicians", lambda: {})
        monkeypatch.setattr(device_admin, "build_device_admin_rows", lambda *a, **k: list(ROWS))
        app = _CapturingApp()
        device_admin.register(app)
        rows, _cols, error, summary, _empty = app.functions["populate_device_admin"](
            {"route": "admin_devices"}, "", "all", "p2", None, "stale", "all", "all"
        )
        assert error is None
        assert devices(rows) == ["29004"]
        assert summary == "Showing 1 of 4 devices — 3 active, 1 inactive"


class _CapturingApp:
    def __init__(self):
        self.functions = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions[fn.__name__] = fn
            return fn

        return decorator
