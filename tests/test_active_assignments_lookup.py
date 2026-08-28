"""One bulk lookup for the Technician column, not 120 per-device queries.

`get_assigned_technician` answers for a single device, which is right for the
assignment drawer and wrong for a table of every RTL in the fleet. Device
Management renders 120 rows from one fleet-wide freshness query; the
technician beside each of them has to arrive the same way.
"""
from unittest.mock import Mock

import pytest
from sqlalchemy import text

import repositories.plant_monitoring_repository as repo
from db.engine import session_scope
from services import prototype_assignments
from services.prototype_assignments import (
    assign_technician,
    assigned_technicians,
    clear_all_assignments,
)
from services.prototype_users import clear_all_users, upsert_user
from tests.test_device_assign import _seed_device


class TestServiceWrapper:
    def test_delegates_to_the_repository_without_reshaping(self, monkeypatch):
        lookup = Mock(return_value={"device-1": "bob"})
        monkeypatch.setattr(repo, "list_active_assignments", lookup)
        assert assigned_technicians() == {"device-1": "bob"}
        lookup.assert_called_once_with()

    def test_is_not_the_per_device_call_in_a_loop(self, monkeypatch):
        """Guards the reason this exists: a wrapper that looped
        `get_active_device_assignment` would satisfy the shape and reintroduce
        the 120 queries."""
        per_device = Mock()
        monkeypatch.setattr(repo, "get_active_device_assignment", per_device)
        monkeypatch.setattr(repo, "list_active_assignments", Mock(return_value={}))
        assigned_technicians()
        per_device.assert_not_called()


class TestAgainstTheDatabase:
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    def setup_method(self):
        with session_scope() as session:
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.audit_log"))
        clear_all_assignments()
        clear_all_users()
        self.admin_id = repo.create_or_update_user(
            username="bulk-admin",
            full_name="bulk-admin",
            role="administrator",
            status="active",
        ).user_id
        upsert_user("bob", "bob@example.com", "technician", "active", actor_user_id=self.admin_id)
        upsert_user("carol", "carol@example.com", "technician", "active", actor_user_id=self.admin_id)
        _seed_device("device-1")
        _seed_device("device-2")
        _seed_device("device-3")

    def test_no_assignments_is_an_empty_mapping_not_an_error(self):
        assert repo.list_active_assignments() == {}

    def test_returns_every_active_assignment_in_one_call(self):
        assign_technician("device-1", "bob", actor_user_id=self.admin_id)
        assign_technician("device-2", "carol", actor_user_id=self.admin_id)
        assert repo.list_active_assignments() == {"device-1": "bob", "device-2": "carol"}

    def test_unassigned_devices_are_absent_rather_than_mapped_to_none(self):
        """Absence is what the row builder reads as "Unassigned"; a None value
        would make every caller test for two empty cases."""
        assign_technician("device-1", "bob", actor_user_id=self.admin_id)
        assert "device-3" not in repo.list_active_assignments()

    def test_an_ended_assignment_is_not_reported_as_current(self):
        assign_technician("device-1", "bob", actor_user_id=self.admin_id)
        assign_technician("device-1", "carol", actor_user_id=self.admin_id)
        assert repo.list_active_assignments()["device-1"] == "carol"

    def test_agrees_with_the_per_device_query_it_replaces(self):
        """Two definitions of "currently assigned" would eventually disagree;
        this pins them together."""
        assign_technician("device-1", "bob", actor_user_id=self.admin_id)
        assign_technician("device-2", "carol", actor_user_id=self.admin_id)
        bulk = repo.list_active_assignments()
        for device_id in ("device-1", "device-2", "device-3"):
            one = repo.get_active_device_assignment(device_id)
            assert bulk.get(device_id) == (one.username if one else None)
