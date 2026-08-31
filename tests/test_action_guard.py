"""The single enforcement entry point for device actions (ROLE-3 Task 11).

TWO QUESTIONS, COMPOSED HERE. `may_perform_action` answers the pure ROLE
question and knows nothing about assignments; `scope_for` answers the
assignment question and knows nothing about actions. This module is the only
place they meet, which is why a callback never has to — and must never —
compare a role or decide ownership itself.
"""
from __future__ import annotations

import pytest

from services import action_guard
from services.auth_service import AuthenticatedUser
from services.authorization import (
    AuthorizationError,
    DEACTIVATE_RTL,
    EXPORT_DATA,
    MANAGE_ASSIGNMENT,
    PROGRAM_RTL,
    REGISTER_DEVICE,
    TOGGLE_MESSAGE_FORWARDING,
)
from services.device_scope import DeviceScope

MUTATING_ACTIONS = [PROGRAM_RTL, TOGGLE_MESSAGE_FORWARDING, DEACTIVATE_RTL]


def _user(role: str, *, user_id: int = 7) -> AuthenticatedUser:
    return AuthenticatedUser(user_id=user_id, username="u", full_name="U", role=role)


def _patch_scope(monkeypatch, scope: DeviceScope, calls: list | None = None):
    """Replace the assignment read. `calls` records that it happened."""

    def _scope_for(user):
        if calls is not None:
            calls.append(user)
        return scope

    monkeypatch.setattr(action_guard, "scope_for", _scope_for)


class TestAdministrator:
    @pytest.mark.parametrize("action", MUTATING_ACTIONS + [MANAGE_ASSIGNMENT])
    def test_may_act_on_any_device(self, monkeypatch, action):
        _patch_scope(monkeypatch, DeviceScope(None))
        action_guard.require_action(_user("administrator"), action, device_id="d1")

    @pytest.mark.parametrize("action", MUTATING_ACTIONS + [MANAGE_ASSIGNMENT])
    def test_needs_no_assignment_lookup(self, monkeypatch, action):
        """An action the role may perform universally must not pay for an
        assignment read to discover that.

        Checked by recording calls rather than by timing: the guard tests the
        any-device set first and only resolves assignment if that fails.
        """
        calls = []
        _patch_scope(monkeypatch, DeviceScope(None), calls)

        action_guard.require_action(_user("administrator"), action, device_id="d1")

        assert calls == []


class TestTechnician:
    @pytest.mark.parametrize("action", MUTATING_ACTIONS)
    def test_may_act_on_an_assigned_device(self, monkeypatch, action):
        _patch_scope(monkeypatch, DeviceScope(frozenset({"d1"})))
        action_guard.require_action(_user("technician"), action, device_id="d1")

    @pytest.mark.parametrize("action", MUTATING_ACTIONS)
    def test_may_not_act_on_an_unassigned_device(self, monkeypatch, action):
        _patch_scope(monkeypatch, DeviceScope(frozenset({"d1"})))
        with pytest.raises(AuthorizationError):
            action_guard.require_action(_user("technician"), action, device_id="d2")

    @pytest.mark.parametrize("action", MUTATING_ACTIONS)
    def test_with_no_assignments_may_act_on_nothing(self, monkeypatch, action):
        """EMPTY scope, not unrestricted. A technician with zero assignments
        is the case a fail-open bug would hand the whole fleet to."""
        _patch_scope(monkeypatch, DeviceScope(frozenset()))
        with pytest.raises(AuthorizationError):
            action_guard.require_action(_user("technician"), action, device_id="d1")

    def test_may_not_manage_assignments_even_on_an_assigned_device(self, monkeypatch):
        """Assignment is what GRANTS their authority; managing it would let a
        technician widen their own scope."""
        _patch_scope(monkeypatch, DeviceScope(frozenset({"d1"})))
        with pytest.raises(AuthorizationError):
            action_guard.require_action(
                _user("technician"), MANAGE_ASSIGNMENT, device_id="d1"
            )

    def test_may_export_without_an_assignment_lookup(self, monkeypatch):
        """Export is open to every role with no assignment condition, so no
        assignment is read for a technician either.

        ADR-013: this used to go through `require_action(..., device_id="d1")`
        and assert the read was skipped. The device_id was always inert — the
        assertion it existed to make is now structural, because
        `require_capability` has no device to read an assignment against. The
        claim is unchanged; the guard proving it is the honest one.
        """
        calls = []
        _patch_scope(monkeypatch, DeviceScope(frozenset()), calls)

        action_guard.require_capability(_user("technician"), EXPORT_DATA)

        assert calls == []

    def test_authorization_is_keyed_on_user_id_not_username(self, monkeypatch):
        """Invariant 2. The guard hands the whole identity to `scope_for`,
        which keys on user_id; nothing here may key on the login string."""
        seen = []
        _patch_scope(monkeypatch, DeviceScope(frozenset({"d1"})), seen)

        user = _user("technician", user_id=99)
        action_guard.require_action(user, PROGRAM_RTL, device_id="d1")

        assert [u.user_id for u in seen] == [99]


class TestGeneral:
    """Invariant 3: unrestricted visibility is not authority."""

    @pytest.mark.parametrize("action", MUTATING_ACTIONS + [MANAGE_ASSIGNMENT])
    def test_may_not_mutate_anything(self, monkeypatch, action):
        _patch_scope(monkeypatch, DeviceScope(None))
        with pytest.raises(AuthorizationError):
            action_guard.require_action(_user("general"), action, device_id="d1")

    def test_unrestricted_scope_does_not_grant_action_authority(self, monkeypatch):
        """The specific confusion this guards against: General's scope is
        UNRESTRICTED, the same value an administrator gets. If the guard ever
        derived authority from scope instead of role, this would pass."""
        _patch_scope(monkeypatch, DeviceScope(None))
        assert DeviceScope(None).allows("d1") is True
        with pytest.raises(AuthorizationError):
            action_guard.require_action(_user("general"), PROGRAM_RTL, device_id="d1")

    def test_may_still_export(self, monkeypatch):
        """Invariant 3 holds through ADR-013: General mutates nothing and
        still exports. Only the guard changed, not the permission."""
        _patch_scope(monkeypatch, DeviceScope(None))
        action_guard.require_capability(_user("general"), EXPORT_DATA)


class TestFailClosed:
    def test_no_user_is_refused(self):
        with pytest.raises(AuthorizationError):
            action_guard.require_action(None, PROGRAM_RTL, device_id="d1")

    def test_no_user_is_refused_without_an_assignment_lookup(self, monkeypatch):
        calls = []
        _patch_scope(monkeypatch, DeviceScope(None), calls)
        with pytest.raises(AuthorizationError):
            action_guard.require_action(None, PROGRAM_RTL, device_id="d1")
        assert calls == []

    def test_unknown_action_is_refused(self, monkeypatch):
        _patch_scope(monkeypatch, DeviceScope(None))
        with pytest.raises(AuthorizationError):
            action_guard.require_action(
                _user("administrator"), "launch_missiles", device_id="d1"
            )

    @pytest.mark.parametrize("role", ["unknown", "Administrator", "", "superuser"])
    def test_an_unrecognised_role_is_refused(self, monkeypatch, role):
        _patch_scope(monkeypatch, DeviceScope(None))
        with pytest.raises(AuthorizationError):
            action_guard.require_action(_user(role), PROGRAM_RTL, device_id="d1")

    def test_device_id_is_keyword_only(self, monkeypatch):
        """Invariant 8 at this boundary: the target cannot be passed by
        accident of position."""
        _patch_scope(monkeypatch, DeviceScope(None))
        with pytest.raises(TypeError):
            action_guard.require_action(_user("administrator"), PROGRAM_RTL, "d1")


class TestRefusalIsDistinctFromABadIdentifier:
    """ROLE-1 froze this, and it matters most here.

    `assign_device_to_user` raises ValueError for an unknown username. A
    caller that wrapped the whole mutation in `except ValueError` to render
    'invalid input' would silently turn every refusal into a validation
    message — and log nothing.
    """

    def test_authorization_error_is_not_a_value_error(self):
        assert not issubclass(AuthorizationError, ValueError)

    def test_catching_value_error_does_not_swallow_a_refusal(self, monkeypatch):
        _patch_scope(monkeypatch, DeviceScope(None))
        with pytest.raises(AuthorizationError):
            try:
                action_guard.require_action(
                    _user("general"), PROGRAM_RTL, device_id="d1"
                )
            except ValueError:  # pragma: no cover - must not fire
                pytest.fail("a refusal was caught as a bad identifier")


class TestTheGuardOwnsTheRule:
    def test_the_guard_module_compares_no_role_strings(self):
        """The rule lives in the policy table, not in this module.

        A role literal here would mean the matrix had been partly copied out
        of `authorization.py`, which is how two answers to one question start.
        """
        import pathlib

        source = pathlib.Path(action_guard.__file__).read_text(encoding="utf-8")
        code = [
            line
            for line in source.splitlines()
            if not line.strip().startswith("#")
        ]
        body = "\n".join(code)
        # Strip the module docstring before looking for role literals in code.
        for role in ('"administrator"', "'administrator'", '"technician"', "'technician'"):
            assert role not in body.split('"""')[-1], role


class TestRequireCapability:
    """The device-less guard.

    `require_action` cannot express registration: it takes a device_id and
    resolves an assignment against it, and at registration time no device
    exists. This guard answers the role question alone and must never touch
    the assignment read to do it.
    """

    def test_administrator_passes(self, monkeypatch):
        calls = []
        _patch_scope(monkeypatch, DeviceScope(None), calls)

        action_guard.require_capability(_user("administrator"), REGISTER_DEVICE)

        assert calls == [], "a device-less capability must not resolve a scope"

    @pytest.mark.parametrize("role", ["technician", "general"])
    def test_other_roles_are_refused(self, monkeypatch, role):
        calls = []
        _patch_scope(monkeypatch, DeviceScope(None), calls)

        with pytest.raises(AuthorizationError):
            action_guard.require_capability(_user(role), REGISTER_DEVICE)

        assert calls == []

    def test_no_user_is_refused(self):
        with pytest.raises(AuthorizationError):
            action_guard.require_capability(None, REGISTER_DEVICE)

    def test_unknown_capability_is_refused(self):
        with pytest.raises(AuthorizationError):
            action_guard.require_capability(_user("administrator"), "read_minds")

    @pytest.mark.parametrize("role", ["Administrator", "", "admin"])
    def test_an_unrecognised_role_is_refused(self, role):
        with pytest.raises(AuthorizationError):
            action_guard.require_capability(_user(role), REGISTER_DEVICE)
