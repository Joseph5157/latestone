"""Unit tests for services.hierarchy_service."""
from __future__ import annotations

import pytest

from repositories.plant_monitoring_repository import (
    DevicePath,
    DeviceRecord,
    PlantRecord,
    TransformerRecord,
)
from services import hierarchy_service as svc
from services.device_scope import UNRESTRICTED


def _plant(plant_id: str, status: str = "active") -> PlantRecord:
    return PlantRecord(plant_id, f"Plant {plant_id}", "Testland", 0.0, 0.0, 100.0, "Gas", status)


def _transformer(tid: str, plant_id: str, status: str = "active") -> TransformerRecord:
    return TransformerRecord(tid, plant_id, "tt01", status)


def _device(did: str, tid: str, status: str = "active") -> DeviceRecord:
    return DeviceRecord(did, tid, "29001", status)


class TestActiveFiltering:
    def test_list_plants_excludes_inactive_by_default(self, monkeypatch):
        monkeypatch.setattr(
            svc.repo, "list_plants", lambda: [_plant("a"), _plant("b", "inactive")]
        )
        assert [p.plant_id for p in svc.list_plants()] == ["a"]

    def test_list_plants_can_include_inactive(self, monkeypatch):
        monkeypatch.setattr(
            svc.repo, "list_plants", lambda: [_plant("a"), _plant("b", "inactive")]
        )
        assert len(svc.list_plants(include_inactive=True)) == 2

    def test_list_transformers_excludes_inactive_by_default(self, monkeypatch):
        monkeypatch.setattr(
            svc.repo,
            "list_transformers",
            lambda plant_id: [_transformer("t1", "a"), _transformer("t2", "a", "inactive")],
        )
        assert [t.transformer_id for t in svc.list_transformers("a")] == ["t1"]

    def test_list_devices_excludes_inactive_by_default(self, monkeypatch):
        monkeypatch.setattr(
            svc.repo,
            "list_devices",
            lambda tid, *, allowed_device_ids: [
                _device("d1", "t1"), _device("d2", "t1", "inactive")
            ],
        )
        assert [d.device_id for d in svc.list_devices("t1", scope=UNRESTRICTED)] == ["d1"]


class TestParentValidation:
    def test_transformer_in_correct_plant_is_returned(self, monkeypatch):
        monkeypatch.setattr(svc.repo, "get_transformer", lambda tid: _transformer("t1", "a"))
        assert svc.get_transformer_in_plant("a", "t1") is not None

    def test_transformer_in_wrong_plant_returns_none(self, monkeypatch):
        """Confused-deputy guard: valid ID, wrong parent."""
        monkeypatch.setattr(svc.repo, "get_transformer", lambda tid: _transformer("t1", "a"))
        assert svc.get_transformer_in_plant("b", "t1") is None

    def test_unknown_transformer_returns_none(self, monkeypatch):
        monkeypatch.setattr(svc.repo, "get_transformer", lambda tid: None)
        assert svc.get_transformer_in_plant("a", "t9") is None

    def test_device_in_wrong_transformer_returns_none(self, monkeypatch):
        monkeypatch.setattr(svc.repo, "get_device", lambda did: _device("d1", "t1"))
        assert svc.get_device_in_transformer("t2", "d1") is None

    def test_device_in_correct_transformer_is_returned(self, monkeypatch):
        monkeypatch.setattr(svc.repo, "get_device", lambda did: _device("d1", "t1"))
        assert svc.get_device_in_transformer("t1", "d1") is not None


class TestDeviceContext:
    def test_returns_path_for_known_device(self, monkeypatch):
        path = DevicePath("p1", "Plant One", "t1", "aa12", "d1", "29017", "active")
        monkeypatch.setattr(svc.repo, "get_device_breadcrumb", lambda did: path)
        assert svc.get_device_context("d1") == path

    def test_returns_none_for_unknown_device(self, monkeypatch):
        monkeypatch.setattr(svc.repo, "get_device_breadcrumb", lambda did: None)
        assert svc.get_device_context("nope") is None
