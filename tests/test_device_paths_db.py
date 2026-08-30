"""Batched device-path label lookup (ADR-008, Phase 9).

The read Command Center uses to name the assets on its event rows. Runs
against a disposable schema — never the developer's real
plant_monitoring.* tables. See tests/conftest.py::isolated_schema.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import hierarchy_service
from services.device_scope import DeviceScope

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]


def _seed() -> None:
    """Two plants, three transformers, four devices — one of them inactive."""
    with session_scope() as session:
        for plant_id, name in (("dp-p1", "Kariba North"), ("dp-p2", "Kendal")):
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.plants "
                    f"(plant_id, name, country, latitude, longitude) "
                    f"VALUES (:plant_id, :name, 'Testland', 0, 0) "
                    f"ON CONFLICT (plant_id) DO NOTHING"
                ),
                {"plant_id": plant_id, "name": name},
            )
        for tid, plant_id, code in (
            ("dp-t1", "dp-p1", "aa12"),
            ("dp-t2", "dp-p1", "ch02"),
            ("dp-t3", "dp-p2", "ru01"),
        ):
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.transformers "
                    f"(transformer_id, plant_id, transformer_code) "
                    f"VALUES (:tid, :plant_id, :code) "
                    f"ON CONFLICT (transformer_id) DO NOTHING"
                ),
                {"tid": tid, "plant_id": plant_id, "code": code},
            )
        for did, tid, code, status in (
            ("dp-d1", "dp-t1", "29017", "active"),
            ("dp-d2", "dp-t2", "29002", "active"),
            ("dp-d3", "dp-t3", "29104", "active"),
            ("dp-d4", "dp-t1", "29900", "inactive"),
        ):
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.devices "
                    f"(device_id, transformer_id, device_code, status) "
                    f"VALUES (:did, :tid, :code, :status) "
                    f"ON CONFLICT (device_id) DO NOTHING"
                ),
                {"did": did, "tid": tid, "code": code, "status": status},
            )


class TestListDevicePaths:
    def test_resolves_the_whole_label_path_for_each_device(self):
        _seed()
        paths = {
            p.device_id: p
            for p in repo.list_device_paths(
                ["dp-d1", "dp-d3"], allowed_device_ids=None
            )
        }

        assert paths["dp-d1"].device_code == "29017"
        assert paths["dp-d1"].transformer_code == "aa12"
        assert paths["dp-d1"].plant_name == "Kariba North"
        assert paths["dp-d3"].plant_name == "Kendal"
        assert paths["dp-d3"].transformer_code == "ru01"

    def test_unknown_ids_are_simply_absent(self):
        """A caller labels what it can and keeps the rest. Raising would let
        one deleted device blank a whole panel of real events."""
        _seed()
        paths = repo.list_device_paths(
            ["dp-d1", "no-such-device"], allowed_device_ids=None
        )
        assert [p.device_id for p in paths] == ["dp-d1"]

    def test_empty_input_issues_no_query_and_returns_nothing(self):
        assert repo.list_device_paths([], allowed_device_ids=None) == []

    def test_inactive_devices_still_resolve(self):
        """ADR-008: this names an event that already happened, so the
        active-only rule that governs 'what is selectable for monitoring'
        does not apply. A device deactivated after its event keeps its
        label."""
        _seed()
        paths = repo.list_device_paths(["dp-d4"], allowed_device_ids=None)
        assert [p.device_code for p in paths] == ["29900"]

    def test_scope_is_enforced_in_sql_not_by_the_caller(self):
        _seed()
        paths = repo.list_device_paths(
            ["dp-d1", "dp-d2", "dp-d3"],
            allowed_device_ids=frozenset({"dp-d2"}),
        )
        assert [p.device_id for p in paths] == ["dp-d2"]

    def test_empty_scope_matches_nothing(self):
        """An EMPTY frozenset is a real constraint, not 'unrestricted' —
        collapsing the two would hand an unassigned technician the fleet."""
        _seed()
        assert (
            repo.list_device_paths(["dp-d1"], allowed_device_ids=frozenset())
            == []
        )


class TestHierarchyServiceWrapper:
    def test_wrapper_passes_scope_through(self):
        _seed()
        scope = DeviceScope(device_ids=frozenset({"dp-d3"}))
        paths = hierarchy_service.list_device_paths(
            ["dp-d1", "dp-d3"], scope=scope
        )
        assert [p.device_id for p in paths] == ["dp-d3"]

    def test_wrapper_does_not_apply_the_active_only_default(self):
        """Unlike list_devices/list_transformers. See ADR-008 Phase 9: an
        event's label is not a claim that the asset is still selectable."""
        _seed()
        paths = hierarchy_service.list_device_paths(
            ["dp-d4"], scope=DeviceScope(device_ids=None)
        )
        assert [p.device_id for p in paths] == ["dp-d4"]
