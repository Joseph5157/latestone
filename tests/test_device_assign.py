"""Tests for the device assignment drawer — layout, technician assignment.

All tests exercise pure logic (no Dash runtime, no database).
"""
from __future__ import annotations

import pytest

from callbacks.device_assign import (
    assign_drawer_open_state,
    find_device_row,
)
from components.assign_device_drawer import assign_device_drawer
from services.prototype_users import (
    clear_all_users,
    upsert_user,
    get_technician_options,
)
from services.prototype_assignments import (
    assign_technician,
    unassign_technician,
    get_assigned_technician,
    list_devices_for_technician,
    clear_all_assignments,
)
from repositories.plant_monitoring_repository import list_assignment_history
from repositories import plant_monitoring_repository as repo
from db.engine import session_scope
from sqlalchemy import text


def _seed_device(device_id: str, plant_id: str = "test-p1", transformer_id: str = "test-p1-t1") -> None:
    """Insert a minimal plant/transformer/device row so device_id satisfies
    user_device_assignments' FK to devices. Idempotent â€” safe to call once
    per test against the module-shared isolated_schema.
    """
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants (plant_id, name, country, latitude, longitude) "
                f"VALUES (:plant_id, 'Test Plant', 'Testland', 0, 0) "
                f"ON CONFLICT (plant_id) DO NOTHING"
            ),
            {"plant_id": plant_id},
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers (transformer_id, plant_id, transformer_code) "
                f"VALUES (:transformer_id, :plant_id, 't1') "
                f"ON CONFLICT (transformer_id) DO NOTHING"
            ),
            {"transformer_id": transformer_id, "plant_id": plant_id},
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.devices (device_id, transformer_id, device_code) "
                f"VALUES (:device_id, :transformer_id, :device_id) "
                f"ON CONFLICT (device_id) DO NOTHING"
            ),
            {"device_id": device_id, "transformer_id": transformer_id},
        )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

class TestAssignDrawerLayout:
    def test_layout_returns_div(self):
        drawer = assign_device_drawer()
        assert hasattr(drawer, "children")

    def test_layout_has_overlay(self):
        drawer = assign_device_drawer()
        ids = _collect_ids(drawer)
        assert "assign-drawer-overlay" in ids

    def test_layout_has_panel(self):
        drawer = assign_device_drawer()
        assert "assign-drawer__panel" in str(drawer)

    def test_layout_has_device_info_section(self):
        drawer = assign_device_drawer()
        assert "assign-drawer-device-code" in str(drawer)
        assert "assign-drawer-current-transformer" in str(drawer)
        assert "assign-drawer-current-plant" in str(drawer)

    def test_layout_has_technician_dropdown(self):
        drawer = assign_device_drawer()
        ids = _collect_ids(drawer)
        assert "assign-technician" in ids

    def test_asset_assignment_controls_are_gone(self):
        """ENT-5 D1/D2: the mock asset-assignment section never changed the
        real hierarchy, so its controls must not exist any more."""
        drawer = assign_device_drawer()
        ids = _collect_ids(drawer)
        assert "assign-plant" not in ids
        assert "assign-transformer" not in ids
        assert "Asset Assignment" not in str(drawer)

    def test_layout_has_footer_cancel_button(self):
        drawer = assign_device_drawer()
        ids = _collect_ids(drawer)
        assert "assign-close-btn" in ids

    def test_confirm_button_has_no_prototype_suffix(self):
        """ENT-5 D4: truthfulness lives in the boundary notice, not the
        action label."""
        drawer = assign_device_drawer()
        text = str(drawer)
        assert "Confirm Assignment" in text
        assert "(Prototype)" not in text

    def test_layout_has_confirm_button(self):
        drawer = assign_device_drawer()
        ids = _collect_ids(drawer)
        assert "assign-confirm-btn" in ids

    def test_layout_has_cancel_button(self):
        drawer = assign_device_drawer()
        ids = _collect_ids(drawer)
        assert "assign-cancel-btn" in ids

    def test_layout_has_hidden_device_store(self):
        drawer = assign_device_drawer()
        ids = _collect_ids(drawer)
        assert "assign-device-hidden-id" in ids

    def test_layout_has_boundary_notice(self):
        """ENT-5: the notice discloses what is and is not connected —
        technician assignment persists; identity system and hierarchy do
        not change."""
        drawer = assign_device_drawer()
        text = str(drawer)
        assert "Assignment is stored and audited" in text
        assert "No identity-system or hierarchy change" in text

    def test_layout_has_technician_assignment_section(self):
        drawer = assign_device_drawer()
        text = str(drawer)
        assert "Technician Assignment" in text

    def test_layout_has_technician_empty_state(self):
        drawer = assign_device_drawer()
        ids = _collect_ids(drawer)
        assert "assign-technician-empty" in ids

    def test_layout_has_header_grammar(self):
        """ENT-5: eyebrow / title / description header, shared with the
        other operational drawers."""
        drawer = assign_device_drawer()
        text = str(drawer)
        assert "assign-drawer__eyebrow" in text
        assert "Assign Device" in text
        assert "assign-drawer__description" in text

    def test_layout_has_result_slot(self):
        """ENT-5 D3: every confirm renders its outcome into a result slot."""
        drawer = assign_device_drawer()
        ids = _collect_ids(drawer)
        assert "assign-result" in ids
        assert "assign-close-btn" in ids


class TestTechnicianAssignmentPersistence:
    # assign_technician()/unassign_technician()/etc are database-backed
    # (DB-3); run against the isolated test schema (tests/conftest.py),
    # never the real user_device_assignments table.
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    def setup_method(self):
        with session_scope() as session:
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.audit_log"))
        clear_all_assignments()
        clear_all_users()
        # AUD-1: service-level writes require an authenticated actor; create
        # one at repository level (no audit row) before any audited call.
        self.admin_id = repo.create_or_update_user(
            username="assign-admin",
            full_name="assign-admin",
            role="administrator",
            status="active",
        ).user_id
        upsert_user("bob", "bob@example.com", "technician", "active", actor_user_id=self.admin_id)
        upsert_user("carol", "carol@example.com", "technician", "active", actor_user_id=self.admin_id)
        upsert_user("dave", "dave@example.com", "general", "active", actor_user_id=self.admin_id)
        _seed_device("device-1")
        _seed_device("device-2")

    def test_no_assignment_returns_none(self):
        assert get_assigned_technician("device-1") is None

    def test_assignment_persists_across_calls(self):
        assign_technician("device-1", "bob", actor_user_id=self.admin_id)
        assert get_assigned_technician("device-1") == "bob"

    def test_assignment_survives_a_separate_process(self, isolated_schema):
        import os
        import subprocess
        import sys

        assign_technician("device-1", "bob", actor_user_id=self.admin_id)

        env = dict(os.environ)
        env["PLANT_MONITORING_SCHEMA"] = isolated_schema
        result = subprocess.run(
            [sys.executable, "-c",
             "from services.prototype_assignments import get_assigned_technician; "
             "print(get_assigned_technician('device-1') or 'MISSING')"],
            cwd=os.getcwd(), env=env, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "bob"

    def test_one_technician_can_own_multiple_devices(self):
        assign_technician("device-1", "bob", actor_user_id=self.admin_id)
        assign_technician("device-2", "bob", actor_user_id=self.admin_id)
        assert sorted(list_devices_for_technician("bob")) == ["device-1", "device-2"]

    def test_reassignment_closes_old_and_creates_new_active_row(self):
        assign_technician("device-1", "bob", actor_user_id=self.admin_id)
        assign_technician("device-1", "carol", actor_user_id=self.admin_id)
        assert get_assigned_technician("device-1") == "carol"

        history = list_assignment_history("device-1")
        assert [h.username for h in history] == ["bob", "carol"]
        assert history[0].ended_at is not None
        assert history[1].ended_at is None

    def test_assigning_same_technician_twice_does_not_duplicate_history(self):
        assign_technician("device-1", "bob", actor_user_id=self.admin_id)
        assign_technician("device-1", "bob", actor_user_id=self.admin_id)
        history = list_assignment_history("device-1")
        assert len(history) == 1
        assert history[0].ended_at is None

    def test_non_technician_cannot_be_assigned(self):
        with pytest.raises(ValueError):
            assign_technician("device-1", "dave", actor_user_id=self.admin_id)
        assert get_assigned_technician("device-1") is None

    def test_unassign_clears_active_assignment(self):
        assign_technician("device-1", "bob", actor_user_id=self.admin_id)
        unassign_technician("device-1", actor_user_id=self.admin_id)
        assert get_assigned_technician("device-1") is None

    def test_unassign_when_nothing_assigned_is_a_safe_no_op(self):
        unassign_technician("device-1", actor_user_id=self.admin_id)
        assert get_assigned_technician("device-1") is None

    def test_device_to_transformer_relationship_is_unchanged(self):
        # Technician assignment must never move the device in the hierarchy:
        # devices.transformer_id keeps its seeded value after an assignment.
        assign_technician("device-1", "bob", actor_user_id=self.admin_id)
        with session_scope() as session:
            row = session.execute(
                text(
                    f"SELECT transformer_id FROM {repo._SCHEMA}.devices "
                    "WHERE device_id = 'device-1'"
                )
            ).scalar()
        assert row == "test-p1-t1"


# ---------------------------------------------------------------------------
# Technician options from prototype users
# ---------------------------------------------------------------------------

class TestTechnicianOptions:
    # clear_all_users()/upsert_user() are database-backed (DB-2); runs against
    # the isolated test schema (tests/conftest.py), never the real users table.
    # This class shares that schema (module-scoped) with
    # TestTechnicianAssignmentPersistence below, so assignment rows left by
    # that class's tests must be cleared first â€” user_device_assignments FKs
    # to users.user_id, and clear_all_users() alone would violate it (DB-3).
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    def setup_method(self):
        with session_scope() as session:
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.audit_log"))
        clear_all_assignments()
        clear_all_users()
        self.admin_id = repo.create_or_update_user(
            username="assign-admin",
            full_name="assign-admin",
            role="administrator",
            status="active",
        ).user_id

    def test_technician_options_include_only_technicians(self):
        upsert_user("alice", "", "administrator", "active", actor_user_id=self.admin_id)
        upsert_user("bob", "", "technician", "active", actor_user_id=self.admin_id)
        upsert_user("charlie", "", "general", "active", actor_user_id=self.admin_id)
        options = get_technician_options()
        assert len(options) == 1
        assert options[0]["value"] == "bob"

    def test_technician_options_exclude_inactive(self):
        upsert_user("bob", "", "technician", "inactive", actor_user_id=self.admin_id)
        options = get_technician_options()
        assert len(options) == 0

    def test_technician_options_empty_when_no_technicians(self):
        options = get_technician_options()
        assert options == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_ids(component) -> list[str]:
    """Recursively collect all component IDs from a Dash layout."""
    ids = []
    if hasattr(component, "id") and component.id:
        ids.append(component.id)
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for child in children:
                ids.extend(_collect_ids(child))
        elif children is not None:
            ids.extend(_collect_ids(children))
    return ids
