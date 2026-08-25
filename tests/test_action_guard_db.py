"""Action authorization against real assignment rows (ROLE-3 Task 11).

tests/test_action_guard.py patches `scope_for`, so it states the RULE and is
blind to what the assignment table actually returns. This file patches
nothing: real users, real assignment rows, real reassignment history.

THE CASE THIS FILE EXISTS FOR is reassignment. `assign_device_to_user`
preserves history — it closes the previous active row and inserts a new one —
so after a reassignment the previous technician still has a row in
user_device_assignments naming that device. If the guard ever read assignment
history instead of the CURRENT active assignment, that technician would keep
their authority forever, and no amount of patched-scope testing would notice.

This is the action-layer twin of test_route_scope_db's ended-assignment test.

Runs against a disposable schema — never the developer's real
plant_monitoring.* tables. See tests/conftest.py::isolated_schema.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import action_guard
from services.auth_service import AuthenticatedUser
from services.authorization import (
    AuthorizationError,
    DEACTIVATE_RTL,
    EXPORT_DATA,
    MANAGE_ASSIGNMENT,
    PROGRAM_RTL,
    TOGGLE_MESSAGE_FORWARDING,
)
from services.prototype_users import clear_all_users, upsert_user

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

PLANT_ID = "ag-p01"
TRANSFORMER_ID = "ag-p01-t1"
DEVICE_ID = "ag-d1"
OTHER_DEVICE_ID = "ag-d2"

MUTATING_ACTIONS = [PROGRAM_RTL, TOGGLE_MESSAGE_FORWARDING, DEACTIVATE_RTL]


def _seed_tree() -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants "
                f"(plant_id, name, country, latitude, longitude) "
                f"VALUES (:plant_id, 'Action Guard Plant', 'Testland', 0, 0) "
                f"ON CONFLICT (plant_id) DO NOTHING"
            ),
            {"plant_id": PLANT_ID},
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES (:transformer_id, :plant_id, 't1') "
                f"ON CONFLICT (transformer_id) DO NOTHING"
            ),
            {"transformer_id": TRANSFORMER_ID, "plant_id": PLANT_ID},
        )
        for device_id in (DEVICE_ID, OTHER_DEVICE_ID):
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.devices "
                    f"(device_id, transformer_id, device_code) "
                    f"VALUES (:device_id, :transformer_id, :device_id) "
                    f"ON CONFLICT (device_id) DO NOTHING"
                ),
                {"device_id": device_id, "transformer_id": TRANSFORMER_ID},
            )


def _reset_people() -> None:
    # Audit rows before assignments before users (each FK-references the
    # table created before it in earlier AUD-1 flows).
    with session_scope() as session:
        session.execute(text(f"DELETE FROM {repo._SCHEMA}.audit_log"))
    repo.delete_all_assignments()
    clear_all_users()


def _auditor_id() -> int:
    """AUD-1: service-level user writes need an authenticated actor. This
    one is created directly at repository level (no audit row) and used to
    attribute the fixture users' audit entries.
    """
    return repo.create_or_update_user(
        username="ag-auditor",
        full_name="ag-auditor",
        role="administrator",
        status="active",
    ).user_id


def _make_user(username: str, role: str) -> AuthenticatedUser:
    upsert_user(username, role=role, actor_user_id=_auditor_id())
    record = repo.get_user_by_username(username)
    assert record is not None
    return AuthenticatedUser(
        user_id=record.user_id, username=username, full_name=username, role=role
    )


@pytest.fixture
def people():
    _seed_tree()
    _reset_people()
    return {
        "tech_a": _make_user("ag-tech-a", "technician"),
        "tech_b": _make_user("ag-tech-b", "technician"),
        "admin": _make_user("ag-admin", "administrator"),
        "general": _make_user("ag-general", "general"),
    }


class TestReassignmentHistoryDoesNotGrant:
    """The rule the user asked to be pinned hardest."""

    @pytest.mark.parametrize("action", MUTATING_ACTIONS)
    def test_the_previous_technician_loses_authority(self, people, action):
        """Assigned yesterday, reassigned away today.

        Tech A's history row still names this device. Only the ACTIVE
        assignment may authorize, so Tech A must be refused and Tech B
        allowed — in the same breath, so a guard that returned a stale answer
        for both cannot pass.
        """
        tech_a, tech_b = people["tech_a"], people["tech_b"]
        repo.assign_device_to_user(DEVICE_ID, tech_a.username, None)
        action_guard.require_action(tech_a, action, device_id=DEVICE_ID)

        repo.assign_device_to_user(DEVICE_ID, tech_b.username, None)

        with pytest.raises(AuthorizationError):
            action_guard.require_action(tech_a, action, device_id=DEVICE_ID)
        action_guard.require_action(tech_b, action, device_id=DEVICE_ID)

    def test_the_history_row_really_still_exists(self, people):
        """Guards the guard: if reassignment DELETED the old row, the test
        above would pass for the wrong reason and prove nothing about
        history being ignored."""
        tech_a, tech_b = people["tech_a"], people["tech_b"]
        repo.assign_device_to_user(DEVICE_ID, tech_a.username, None)
        repo.assign_device_to_user(DEVICE_ID, tech_b.username, None)

        with session_scope() as session:
            rows = session.execute(
                text(
                    f"SELECT user_id, ended_at "
                    f"FROM {repo._SCHEMA}.user_device_assignments "
                    f"WHERE device_id = :device_id"
                ),
                {"device_id": DEVICE_ID},
            ).all()

        by_user = {r.user_id: r.ended_at for r in rows}
        assert tech_a.user_id in by_user, "the history row was deleted, not closed"
        assert by_user[tech_a.user_id] is not None, "the old row is still active"
        assert by_user[tech_b.user_id] is None, "the new row should be active"

    @pytest.mark.parametrize("action", MUTATING_ACTIONS)
    def test_an_ended_assignment_grants_nothing(self, people, action):
        """Unassigned outright rather than reassigned: same rule."""
        tech_a = people["tech_a"]
        repo.assign_device_to_user(DEVICE_ID, tech_a.username, None)
        repo.end_active_device_assignment(DEVICE_ID)

        with pytest.raises(AuthorizationError):
            action_guard.require_action(tech_a, action, device_id=DEVICE_ID)

    @pytest.mark.parametrize("action", MUTATING_ACTIONS)
    def test_reassignment_back_restores_authority(self, people, action):
        """The rule is 'current', not 'never held before'."""
        tech_a, tech_b = people["tech_a"], people["tech_b"]
        repo.assign_device_to_user(DEVICE_ID, tech_a.username, None)
        repo.assign_device_to_user(DEVICE_ID, tech_b.username, None)
        repo.assign_device_to_user(DEVICE_ID, tech_a.username, None)

        action_guard.require_action(tech_a, action, device_id=DEVICE_ID)
        with pytest.raises(AuthorizationError):
            action_guard.require_action(tech_b, action, device_id=DEVICE_ID)


class TestTechnicianAgainstRealAssignments:
    @pytest.mark.parametrize("action", MUTATING_ACTIONS)
    def test_assigned_device_is_allowed(self, people, action):
        tech_a = people["tech_a"]
        repo.assign_device_to_user(DEVICE_ID, tech_a.username, None)
        action_guard.require_action(tech_a, action, device_id=DEVICE_ID)

    @pytest.mark.parametrize("action", MUTATING_ACTIONS)
    def test_a_sibling_device_is_refused(self, people, action):
        """Assigned one device does not mean assigned the transformer."""
        tech_a = people["tech_a"]
        repo.assign_device_to_user(DEVICE_ID, tech_a.username, None)
        with pytest.raises(AuthorizationError):
            action_guard.require_action(tech_a, action, device_id=OTHER_DEVICE_ID)

    @pytest.mark.parametrize("action", MUTATING_ACTIONS)
    def test_a_technician_with_no_assignments_is_refused(self, people, action):
        with pytest.raises(AuthorizationError):
            action_guard.require_action(
                people["tech_a"], action, device_id=DEVICE_ID
            )

    def test_may_not_manage_assignment_on_an_assigned_device(self, people):
        tech_a = people["tech_a"]
        repo.assign_device_to_user(DEVICE_ID, tech_a.username, None)
        with pytest.raises(AuthorizationError):
            action_guard.require_action(
                tech_a, MANAGE_ASSIGNMENT, device_id=DEVICE_ID
            )

    def test_may_export_without_any_assignment(self, people):
        action_guard.require_action(
            people["tech_a"], EXPORT_DATA, device_id=DEVICE_ID
        )


class TestOtherRolesAgainstRealAssignments:
    @pytest.mark.parametrize("action", MUTATING_ACTIONS + [MANAGE_ASSIGNMENT])
    def test_administrator_needs_no_assignment_row(self, people, action):
        """No assignment exists for anyone; the administrator still acts."""
        action_guard.require_action(people["admin"], action, device_id=DEVICE_ID)

    @pytest.mark.parametrize("action", MUTATING_ACTIONS + [MANAGE_ASSIGNMENT])
    def test_general_is_refused_even_with_an_assignment_row(self, people, action):
        """Invariant 3, at its sharpest.

        `assign_device_to_user` refuses a non-technician, so General cannot
        even hold an assignment — and would still be refused if they could,
        because the role is denied in the any-device AND assigned-only sets.
        """
        with pytest.raises(ValueError):
            repo.assign_device_to_user(DEVICE_ID, people["general"].username, None)

        with pytest.raises(AuthorizationError):
            action_guard.require_action(
                people["general"], action, device_id=DEVICE_ID
            )

    def test_general_may_still_export(self, people):
        action_guard.require_action(
            people["general"], EXPORT_DATA, device_id=DEVICE_ID
        )
