"""`build_my_rtls_rows` — a Technician's Devices page rows (kept by
SWITCH-OVER-1 when the old Fleet Overview's My RTLs panel was removed)."""
from __future__ import annotations

from types import SimpleNamespace

from callbacks import listings
from services.device_scope import DeviceScope
from services.monitoring_service import fleet_health_from_rows


def _count_label_reads(monkeypatch):
    calls = []

    def paths(ids, *, scope):
        calls.append(list(ids))
        return [SimpleNamespace(device_id=i, device_code=i.upper(), plant_name="P",
                                transformer_code="T") for i in ids]

    monkeypatch.setattr(listings.hierarchy_service, "list_device_paths", paths)
    return calls


def test_empty_scope_issues_no_label_query(monkeypatch):
    calls = _count_label_reads(monkeypatch)
    assert listings.build_my_rtls_rows(DeviceScope(frozenset()), fleet_health_from_rows([])) == []
    assert calls == []


def test_restricted_scope_issues_one_label_query_and_defaults_to_no_data(monkeypatch):
    calls = _count_label_reads(monkeypatch)
    rows = listings.build_my_rtls_rows(
        DeviceScope(frozenset({"d2", "d1"})), fleet_health_from_rows([])
    )
    assert calls == [["d1", "d2"]]
    assert [r["device"] for r in rows] == ["D1", "D2"]
    assert all(r["_state"] == "no_data" for r in rows)
