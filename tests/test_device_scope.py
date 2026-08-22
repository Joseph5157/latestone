"""DeviceScope resolution — the single authority on device visibility."""
from __future__ import annotations

import pytest

from services import device_scope
from services.auth_service import AuthenticatedUser
from services.device_scope import EMPTY, UNRESTRICTED, DeviceScope


def _user(role: str, user_id: int = 7) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id, username="u", full_name="U", role=role
    )


def test_unrestricted_allows_any_device():
    assert UNRESTRICTED.is_unrestricted is True
    assert UNRESTRICTED.allows("anything-at-all") is True


def test_empty_allows_nothing():
    assert EMPTY.is_unrestricted is False
    assert EMPTY.allows("anything-at-all") is False


def test_empty_and_unrestricted_are_not_the_same_state():
    """Invariant 8. If these ever compare equal, an unassigned technician
    inherits the whole fleet."""
    assert EMPTY != UNRESTRICTED
    assert EMPTY.device_ids == frozenset()
    assert UNRESTRICTED.device_ids is None


def test_constrained_scope_allows_only_its_members():
    scope = DeviceScope(device_ids=frozenset({"d1", "d2"}))
    assert scope.allows("d1") is True
    assert scope.allows("d9") is False


def test_administrator_is_unrestricted():
    assert device_scope.scope_for(_user("administrator")) == UNRESTRICTED


def test_general_is_unrestricted():
    """Invariant 3: read-only constrains actions, not sight."""
    assert device_scope.scope_for(_user("general")) == UNRESTRICTED


def test_no_user_is_empty():
    assert device_scope.scope_for(None) == EMPTY


def test_unrecognised_role_is_empty():
    """Default-deny, matching ROUTE_POLICY."""
    assert device_scope.scope_for(_user("Administrator")) == EMPTY
    assert device_scope.scope_for(_user("superuser")) == EMPTY


def test_technician_scope_is_their_active_assignments(monkeypatch):
    seen = {}

    def fake_lookup(user_id):
        seen["user_id"] = user_id
        return ["d1", "d2"]

    monkeypatch.setattr(device_scope.repo, "list_active_device_ids_for_user", fake_lookup)
    scope = device_scope.scope_for(_user("technician", user_id=42))

    assert scope.device_ids == frozenset({"d1", "d2"})
    assert seen["user_id"] == 42, "Invariant 2: resolved by user_id, not username"


def test_technician_with_no_assignments_is_empty_not_unrestricted(monkeypatch):
    monkeypatch.setattr(
        device_scope.repo, "list_active_device_ids_for_user", lambda user_id: []
    )
    scope = device_scope.scope_for(_user("technician"))

    assert scope == EMPTY
    assert scope.is_unrestricted is False


def test_scope_from_session_rejects_pre_role_1_payload():
    assert device_scope.scope_from_session({"authenticated": True}) == EMPTY


def test_scope_from_session_rejects_none():
    assert device_scope.scope_from_session(None) == EMPTY


def test_scope_from_session_resolves_a_valid_administrator_session():
    session = {
        "authenticated": True,
        "user_id": 1,
        "username": "admin",
        "full_name": "Admin",
        "role": "administrator",
    }
    assert device_scope.scope_from_session(session) == UNRESTRICTED


def test_hierarchy_service_list_devices_requires_scope():
    """Invariant 8 at the service boundary."""
    from services import hierarchy_service

    with pytest.raises(TypeError):
        hierarchy_service.list_devices("any-transformer")
