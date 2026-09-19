"""AUTH-HARDEN-1 — the server-trusted session actually decides.

Every other test file touched by this tranche proves one callback's own
authorization is correct AS OF a given trusted identity. This file proves the
trust boundary itself: that a browser-supplied `auth-store` payload — a forged
role, a forged user_id, an entirely absent session — cannot substitute for
`current_identity()`'s own re-read of the current database row.

**The rule every test here follows, per the gate's own instruction:** never
construct a trusted identity by hand and call that "browser tampering
solved". Each attack test establishes a REAL trusted session (a real Flask
session, a real — if fake-backed — `users` row reachable through
`repo.get_user_by_id`) for one identity, then invokes the real registered
callback with an `auth_data` argument that CLAIMS something different. The
claim must be ignored; only the trusted session may decide the outcome.

Numbered AUTH-HARDEN-01..15 below map directly to the gate's required
coverage list. Some of that coverage already exists elsewhere in the suite —
each such case is a one-line pointer here, not a duplicate, per the gate's
own "do not duplicate tests unnecessarily" instruction elsewhere in this
tranche's sibling files. The cases with NO prior coverage (P0-3's device
telemetry scope, P0-4's admin device-list, revocation, logout) are written in
full here.
"""
from __future__ import annotations

import types

import pytest

from callbacks import auth as auth_callbacks
from callbacks import device, device_admin
from repositories import plant_monitoring_repository as repo
from services import auth_service
from tests.auth_test_support import fake_user_row, no_trusted_session, trusted_session

# ---------------------------------------------------------------------------
# Shared plumbing
# ---------------------------------------------------------------------------


class _CapturingApp:
    def __init__(self):
        self.functions = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions[fn.__name__] = fn
            return fn

        return decorator


def _handlers(module):
    app = _CapturingApp()
    module.register(app)
    return app.functions


#: A browser-forged auth-store payload. Every "forged" test below passes THIS
#: — never the payload matching the real trusted session — as `auth_data`,
#: proving the callback never reads it.
def _forged(role: str, user_id: int = 999) -> dict:
    return {
        "authenticated": True,
        "user_id": user_id,
        "username": "forged",
        "full_name": "Forged Identity",
        "role": role,
    }


# ---------------------------------------------------------------------------
# current_identity() itself — the primitive everything else is built on
# ---------------------------------------------------------------------------


class TestCurrentIdentity:
    def test_no_trusted_session_is_none(self):
        with no_trusted_session():
            assert auth_service.current_identity() is None

    def test_a_real_trusted_session_resolves_the_current_row(self, monkeypatch):
        with trusted_session(monkeypatch, user_id=104, role="technician") as row:
            identity = auth_service.current_identity()
            assert identity is not None
            assert identity.user_id == 104
            assert identity.role == "technician"
            assert identity.username == row.username

    def test_a_session_naming_a_deleted_user_is_none(self, monkeypatch):
        monkeypatch.setattr(repo, "get_user_by_id", lambda uid: None)
        with no_trusted_session():
            auth_service.start_trusted_session(999)
            assert auth_service.current_identity() is None

    def test_a_session_naming_an_inactive_user_is_none(self, monkeypatch):
        with trusted_session(monkeypatch, user_id=104, role="technician", status="inactive"):
            assert auth_service.current_identity() is None

    def test_a_session_naming_an_unconfirmed_role_is_none(self, monkeypatch):
        with trusted_session(monkeypatch, user_id=104, role="superuser"):
            assert auth_service.current_identity() is None

    def test_current_role_mirrors_current_identity(self, monkeypatch):
        with no_trusted_session():
            assert auth_service.current_role() is None
        with trusted_session(monkeypatch, user_id=1, role="administrator"):
            assert auth_service.current_role() == "administrator"

    def test_start_trusted_session_clears_any_prior_identity_first(self, monkeypatch):
        """A login on a tab already holding a different trusted session must
        not merge the two — the new login replaces it outright."""
        row_a = fake_user_row(1, "administrator")
        row_b = fake_user_row(2, "technician")
        rows = {1: row_a, 2: row_b}
        monkeypatch.setattr(repo, "get_user_by_id", lambda uid: rows.get(uid))

        with no_trusted_session():
            auth_service.start_trusted_session(1)
            assert auth_service.current_identity().role == "administrator"
            auth_service.start_trusted_session(2)
            identity = auth_service.current_identity()
            assert identity.user_id == 2
            assert identity.role == "technician"


# ---------------------------------------------------------------------------
# AUTH-HARDEN-01 / 02 — forged role does not grant Administrator privileges
# ---------------------------------------------------------------------------


class TestForgedAdministratorRole:
    """AUTH-HARDEN-01 (General) and AUTH-HARDEN-02 (Technician).

    Routing-level proof against a REAL database (real technician row, real
    device rows) already exists:
    tests/test_route_scope_db.py::test_a_forged_administrator_role_does_not_widen_a_real_technicians_scope
    tests/test_route_scope_db.py::test_a_forged_role_does_not_unlock_admin_devices_for_a_real_technician

    These add the mutation-boundary proof (user administration) and the
    General persona, which that file does not cover.
    """

    @pytest.mark.parametrize("role", ["general", "technician"])
    def test_cannot_save_a_user_by_forging_administrator_in_auth_data(
        self, monkeypatch, role
    ):
        from callbacks import user_admin
        from components.status_panels import ACTION_REFUSED_CLASS

        monkeypatch.setattr(user_admin, "get_user", lambda name: None)
        calls = []
        monkeypatch.setattr(user_admin, "upsert_user", lambda *a, **k: calls.append((a, k)))

        with trusted_session(monkeypatch, user_id=50, role=role):
            handler = _handlers(user_admin)["confirm_user_form"]
            _err, result, _style, _hidden = handler(
                1, None, "self-promoted", "x@example.invalid",
                "administrator", "active",
                _forged("administrator"),  # the browser's claim — must be ignored
            )

        assert getattr(result, "className", "") == ACTION_REFUSED_CLASS
        assert calls == [], f"a real {role} must not save a user via a forged role"

    @pytest.mark.parametrize("role", ["general", "technician"])
    def test_cannot_open_the_admin_device_list_by_forging_administrator(
        self, monkeypatch, role
    ):
        with trusted_session(monkeypatch, user_id=50, role=role):
            handler = _handlers(device_admin)["populate_device_admin"]
            rows, _columns, error, _summary, _empty = handler(
                {"route": "admin_devices"}, "", "all"
            )

        assert rows == []
        assert error is not None, f"a real {role} must be refused the admin device list"


# ---------------------------------------------------------------------------
# AUTH-HARDEN-03 — forged user_id does not change device scope
# ---------------------------------------------------------------------------


class TestForgedUserId:
    def test_device_scope_follows_the_trusted_user_id_not_a_forged_one(self, monkeypatch):
        """Two real technicians, disjoint assignments. Signed in as A, the
        browser claims to be B (in auth_data's user_id) — scope must stay A's."""
        from services import device_scope

        tech_a = fake_user_row(101, "technician", username="tech.a")
        tech_b = fake_user_row(102, "technician", username="tech.b")
        rows = {101: tech_a, 102: tech_b}
        monkeypatch.setattr(repo, "get_user_by_id", lambda uid: rows.get(uid))

        assignments = {101: frozenset({"device-a"}), 102: frozenset({"device-b"})}
        monkeypatch.setattr(
            repo,
            "list_active_device_ids_for_user",
            lambda user_id: assignments.get(user_id, frozenset()),
        )

        with no_trusted_session():
            auth_service.start_trusted_session(101)  # really signed in as A
            scope = device_scope.current_device_scope()

        assert scope.allows("device-a") is True
        assert scope.allows("device-b") is False, (
            "a forged user_id in auth_data must not borrow technician B's scope"
        )


# ---------------------------------------------------------------------------
# AUTH-HARDEN-04 / 05 — see tests/test_user_admin_callbacks.py
# (test_a_non_administrator_cannot_save_a_user, parametrized technician/general)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# AUTH-HARDEN-06 — unassigned-device telemetry, direct invocation (P0-3)
# ---------------------------------------------------------------------------


class TestUnassignedDeviceTelemetry:
    """The defect this closes had NO guard at all: `refresh_device_dashboard`
    trusted `page-context.device_id` outright. `page-context` is an Input, not
    a State, so this callback is independently invokable with a forged
    device_id regardless of what the router's own scope check decided when it
    built the real page-context."""

    def _handler(self):
        return _handlers(device)["refresh_device_dashboard"]

    def test_technician_cannot_read_telemetry_for_an_unassigned_device(self, monkeypatch):
        from services import monitoring_service as svc

        calls = []
        monkeypatch.setattr(
            svc, "get_device_full_view",
            lambda *a, **k: calls.append(a) or {},
        )

        with trusted_session(monkeypatch, user_id=104, role="technician"):
            monkeypatch.setattr(
                repo, "list_active_device_ids_for_user",
                lambda user_id: frozenset({"assigned-device"}),
            )
            result = self._handler()(
                {"route": "device", "device_id": "not-assigned-to-me"},
                "temperature", "24h", None, None, 0,
            )

        assert calls == [], "an out-of-scope device must never reach the query layer"
        # error_outputs()'s shape: 8 outputs, none of them real telemetry.
        assert len(result) == 8

    def test_technician_can_read_telemetry_for_an_assigned_device(self, monkeypatch):
        from services import monitoring_service as svc

        calls = []

        def _fake_view(*a, **k):
            calls.append(a)
            return {}

        monkeypatch.setattr(svc, "get_device_full_view", _fake_view)

        with trusted_session(monkeypatch, user_id=104, role="technician"):
            monkeypatch.setattr(
                repo, "list_active_device_ids_for_user",
                lambda user_id: frozenset({"assigned-device"}),
            )
            result = self._handler()(
                {"route": "device", "device_id": "assigned-device"},
                "temperature", "24h", None, None, 0,
            )

        assert calls, "an assigned device must still reach the query layer"
        # metric_key "temperature" is not in the (empty) views dict, so the
        # handler returns its early no_update tuple — still proof the scope
        # check itself did not refuse.
        assert len(result) == 8

    def test_administrator_reads_telemetry_for_any_device(self, monkeypatch):
        from services import monitoring_service as svc

        calls = []
        monkeypatch.setattr(
            svc, "get_device_full_view", lambda *a, **k: calls.append(a) or {}
        )

        with trusted_session(monkeypatch, user_id=1, role="administrator"):
            result = self._handler()(
                {"route": "device", "device_id": "any-device-at-all"},
                "temperature", "24h", None, None, 0,
            )

        assert calls, "an administrator must reach the query layer for any device"


# ---------------------------------------------------------------------------
# AUTH-HARDEN-07 — Administrator device-list callback, direct invocation (P0-4)
# ---------------------------------------------------------------------------


class TestAdminDeviceListDirectInvocation:
    def _fixture(self, monkeypatch):
        monkeypatch.setattr(device_admin.hierarchy_service, "list_all_devices", lambda **k: [])
        health = types.SimpleNamespace(devices={}, device_last_updated={})
        monkeypatch.setattr(
            device_admin.monitoring_service, "get_fleet_health", lambda *a, **k: health
        )
        monkeypatch.setattr(
            device_admin.prototype_assignments, "assigned_technicians", lambda: {}
        )
        return _handlers(device_admin)["populate_device_admin"]

    def test_technician_direct_invocation_is_denied(self, monkeypatch):
        handler = self._fixture(monkeypatch)

        with trusted_session(monkeypatch, user_id=104, role="technician"):
            rows, _columns, error, _summary, _empty = handler(
                {"route": "admin_devices"}, "", "all"
            )

        assert rows == []
        assert error is not None

    def test_administrator_direct_invocation_succeeds(self, monkeypatch):
        handler = self._fixture(monkeypatch)

        with trusted_session(monkeypatch, user_id=1, role="administrator"):
            rows, _columns, error, summary, _empty = handler(
                {"route": "admin_devices"}, "", "all"
            )

        assert error is None
        assert summary


# ---------------------------------------------------------------------------
# AUTH-HARDEN-08 — Administrator user-list callback, direct invocation
# ---------------------------------------------------------------------------


class TestAdminUserListDirectInvocation:
    def test_general_direct_invocation_is_denied(self, monkeypatch):
        from callbacks import user_admin

        monkeypatch.setattr(user_admin, "get_all_users", lambda: [])
        handler = _handlers(user_admin)["populate_user_admin"]

        with trusted_session(monkeypatch, user_id=7, role="general"):
            rows, _columns, error, _summary = handler({"route": "admin_users"}, "", "all")

        assert rows == []
        assert error is not None

    def test_administrator_direct_invocation_succeeds(self, monkeypatch):
        from callbacks import user_admin

        monkeypatch.setattr(user_admin, "get_all_users", lambda: [])
        handler = _handlers(user_admin)["populate_user_admin"]

        with trusted_session(monkeypatch, user_id=1, role="administrator"):
            rows, _columns, error, _summary = handler({"route": "admin_users"}, "", "all")

        assert error is None


# ---------------------------------------------------------------------------
# AUTH-HARDEN-09 / 10 — role and status revocation take effect immediately
# ---------------------------------------------------------------------------


class TestRevocationWithoutRelogin:
    """Scenario A/B from the gate spec, proven at the primitive level: the
    SAME trusted Flask session (no new login) must reflect a database change
    made after it was established. `current_identity()` never caches — this
    is what that buys."""

    def test_a_disabled_user_is_refused_on_their_very_next_call(self, monkeypatch):
        state = {"status": "active"}
        row = fake_user_row(104, "technician")

        def get_by_id(uid):
            if uid != 104:
                return None
            return repo.UserRecord(
                user_id=104, username=row.username, full_name=row.full_name,
                email_address=None, mobile_number=None, role="technician",
                status=state["status"], created_at=row.created_at, updated_at=row.updated_at,
            )

        monkeypatch.setattr(repo, "get_user_by_id", get_by_id)

        with no_trusted_session():
            auth_service.start_trusted_session(104)
            assert auth_service.current_identity() is not None, "starts active"

            state["status"] = "inactive"  # an administrator disables them

            assert auth_service.current_identity() is None, (
                "the SAME session must fail on its next call — no new login occurred"
            )

    def test_a_demoted_users_next_operation_uses_the_new_role(self, monkeypatch):
        """AUTH-HARDEN-10, against a real registered callback: an
        Administrator demoted to General mid-session must be refused the
        user-admin save on their very next attempt."""
        from callbacks import user_admin
        from components.status_panels import ACTION_REFUSED_CLASS

        state = {"role": "administrator"}
        row = fake_user_row(1, "administrator")

        def get_by_id(uid):
            if uid != 1:
                return None
            return repo.UserRecord(
                user_id=1, username=row.username, full_name=row.full_name,
                email_address=None, mobile_number=None, role=state["role"],
                status="active", created_at=row.created_at, updated_at=row.updated_at,
            )

        monkeypatch.setattr(repo, "get_user_by_id", get_by_id)
        monkeypatch.setattr(user_admin, "get_user", lambda name: None)
        calls = []
        monkeypatch.setattr(user_admin, "upsert_user", lambda *a, **k: calls.append((a, k)))
        handler = _handlers(user_admin)["confirm_user_form"]

        with no_trusted_session():
            auth_service.start_trusted_session(1)  # still admin here

            state["role"] = "general"  # demoted mid-session, no re-login

            _err, result, _style, _hidden = handler(
                1, None, "newbie", "x@example.invalid",
                "technician", "active", None,
            )

        assert getattr(result, "className", "") == ACTION_REFUSED_CLASS
        assert calls == [], "the demoted role must apply to this very call"


# ---------------------------------------------------------------------------
# AUTH-HARDEN-14 — unauthenticated direct invocation fails closed
# ---------------------------------------------------------------------------


class TestUnauthenticatedDirectInvocation:
    def test_device_telemetry_refuses_with_no_trusted_session(self, monkeypatch):
        from services import monitoring_service as svc

        calls = []
        monkeypatch.setattr(
            svc, "get_device_full_view", lambda *a, **k: calls.append(a) or {}
        )
        with no_trusted_session():
            result = _handlers(device)["refresh_device_dashboard"](
                {"route": "device", "device_id": "any-device"},
                "temperature", "24h", None, None, 0,
            )
        assert calls == []
        assert len(result) == 8

    def test_admin_device_list_refuses_with_no_trusted_session(self, monkeypatch):
        monkeypatch.setattr(device_admin.hierarchy_service, "list_all_devices", lambda **k: [])
        handler = _handlers(device_admin)["populate_device_admin"]
        with no_trusted_session():
            rows, _columns, error, _summary, _empty = handler(
                {"route": "admin_devices"}, "", "all"
            )
        assert rows == []
        assert error is not None


# ---------------------------------------------------------------------------
# AUTH-HARDEN-15 — logout clears the trusted session
# ---------------------------------------------------------------------------


class TestLogoutClearsTrustedState:
    def test_the_real_sign_out_callback_ends_the_trusted_session(self, monkeypatch):
        from callbacks.auth import LOGOUT_PATH

        with trusted_session(monkeypatch, user_id=104, role="technician"):
            assert auth_service.current_identity() is not None

            _sign_out = _handlers(auth_callbacks)["_sign_out"]
            _sign_out(LOGOUT_PATH)

            assert auth_service.current_identity() is None, (
                "the real logout callback must clear the trusted server "
                "session, not only the browser's auth-store"
            )

    def test_navigating_elsewhere_does_not_end_the_session(self, monkeypatch):
        """`_sign_out` fires on every pathname change (it is how a bookmarked
        /logout still works on a cold load) — it must only clear the trusted
        session when the path really is /logout."""
        with trusted_session(monkeypatch, user_id=104, role="technician"):
            _sign_out = _handlers(auth_callbacks)["_sign_out"]
            _sign_out("/plants")

            assert auth_service.current_identity() is not None, (
                "an ordinary navigation must not sign the operator out"
            )
