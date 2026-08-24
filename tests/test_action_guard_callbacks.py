"""The mutation callbacks go through the guard (ROLE-3 Task 11).

WHY THIS FILE MATTERS MORE THAN IT LOOKS. Today only administrators can reach
the Manage and Assign drawers, and administrators pass every check, so none of
these refusals can currently be triggered through the UI. That is precisely
why they need tests: the wiring is invisible in manual testing and would rot
silently until the day a technician-facing surface exists — which ROLE-3
invariant 10 forbids adding here.

These tests stay role-pure: administrator and general both resolve without an
assignment read, so no database is involved.
"""
from __future__ import annotations

import pytest

from callbacks import device_assign, device_manage, device_register
from services import hierarchy_service

ADMINISTRATOR_SESSION = {
    "authenticated": True,
    "user_id": 1,
    "username": "admin",
    "full_name": "Admin",
    "role": "administrator",
}

GENERAL_SESSION = {
    "authenticated": True,
    "user_id": 7,
    "username": "general",
    "full_name": "General",
    "role": "general",
}

TECHNICIAN_SESSION = {
    "authenticated": True,
    "user_id": 42,
    "username": "tech",
    "full_name": "Tech",
    "role": "technician",
}

#: The pre-ROLE-1 payload: authenticated, but carrying no usable identity.
STALE_SESSION = {"authenticated": True}

DEVICE_ID = "cb-d1"


class _CapturingApp:
    """Collects callbacks by function name instead of registering them."""

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


def _is_refusal(result) -> bool:
    """A refusal renders the shared notice, never the success panel."""
    from components.status_panels import ACTION_REFUSED_CLASS

    return getattr(result, "className", "") == ACTION_REFUSED_CLASS


def _rendered_text(result) -> str:
    return str(result)


# --------------------------------------------------------------------------
# Program RTL
# --------------------------------------------------------------------------


class TestProgramRtl:
    def _call(self, session):
        handler = _handlers(device_manage)["confirm_program_rtl"]
        return handler(1, DEVICE_ID, "uid-1", "t1", "0700000000", session)

    def test_administrator_succeeds(self):
        result = self._call(ADMINISTRATOR_SESSION)
        assert not _is_refusal(result)

    def test_general_is_refused(self):
        assert _is_refusal(self._call(GENERAL_SESSION))

    def test_a_stale_session_is_refused(self):
        """`from_session` rejects the pre-ROLE-1 payload, and the guard
        refuses a None identity rather than treating it as unrestricted."""
        assert _is_refusal(self._call(STALE_SESSION))

    def test_no_session_is_refused(self):
        assert _is_refusal(self._call(None))

    def test_the_refusal_names_no_policy_detail(self):
        """The panel states the outcome. It does not echo the role, the
        action or the device id back at the operator."""
        text = _rendered_text(self._call(GENERAL_SESSION))
        assert "general" not in text.lower()
        assert DEVICE_ID not in text


# --------------------------------------------------------------------------
# Message forwarding
# --------------------------------------------------------------------------


class TestMessageForwarding:
    def _call(self, session, device_id=DEVICE_ID):
        handler = _handlers(device_manage)["confirm_message_forwarding"]
        return handler(1, device_id, "enabled", session)

    def test_administrator_succeeds(self):
        device_manage.clear_mock_device_state()
        result = self._call(ADMINISTRATOR_SESSION)
        assert not _is_refusal(result)
        assert device_manage.get_mock_device_state(DEVICE_ID)["forwarding"] == "enabled"

    def test_general_is_refused_and_changes_nothing(self):
        """The refusal must land BEFORE the state write, not after it."""
        device_manage.clear_mock_device_state()

        assert _is_refusal(self._call(GENERAL_SESSION))

        assert device_manage.get_mock_device_state(DEVICE_ID)["forwarding"] == "disabled"

    def test_no_session_changes_nothing(self):
        device_manage.clear_mock_device_state()
        assert _is_refusal(self._call(None))
        assert device_manage.get_mock_device_state(DEVICE_ID)["forwarding"] == "disabled"


# --------------------------------------------------------------------------
# Deactivate
# --------------------------------------------------------------------------


class TestDeactivateRtl:
    def _call(self, session):
        handler = _handlers(device_manage)["confirm_deactivate_rtl"]
        return handler(1, DEVICE_ID, session)

    def test_administrator_succeeds(self):
        assert not _is_refusal(self._call(ADMINISTRATOR_SESSION))

    def test_general_is_refused(self):
        assert _is_refusal(self._call(GENERAL_SESSION))

    def test_no_session_is_refused(self):
        assert _is_refusal(self._call(None))


# --------------------------------------------------------------------------
# Assignment
# --------------------------------------------------------------------------


class TestConfirmAssignment:
    def _call(self, session, technician=None, transformer_id="t9"):
        handler = _handlers(device_assign)["confirm_assignment"]
        return handler(1, DEVICE_ID, "p1", transformer_id, technician, session)

    def test_general_is_refused_and_assigns_nothing(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            device_assign.prototype_assignments,
            "assign_technician",
            lambda *a, **k: calls.append(a),
        )
        device_assign.clear_mock_assignments()

        self._call(GENERAL_SESSION, technician="someone")

        assert calls == []
        assert device_assign.get_mock_assignment(DEVICE_ID) is None

    def test_technician_may_not_manage_assignment(self, monkeypatch):
        """Assignment is administrator-only even for a technician who holds
        the device: it is what grants their own authority."""
        calls = []
        monkeypatch.setattr(
            device_assign.prototype_assignments,
            "assign_technician",
            lambda *a, **k: calls.append(a),
        )
        # A technician is the one role whose authorization needs an
        # assignment read. Stub it so this file stays free of the database;
        # the real lookup is exercised in tests/test_action_guard_db.py.
        import services.action_guard as guard
        from services.device_scope import DeviceScope

        monkeypatch.setattr(guard, "scope_for", lambda user: DeviceScope(frozenset({DEVICE_ID})))
        device_assign.clear_mock_assignments()

        self._call(TECHNICIAN_SESSION, technician="someone")

        assert calls == []
        assert device_assign.get_mock_assignment(DEVICE_ID) is None

    def test_administrator_still_assigns(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            device_assign.prototype_assignments,
            "assign_technician",
            lambda *a, **k: calls.append(a),
        )
        device_assign.clear_mock_assignments()

        self._call(ADMINISTRATOR_SESSION, technician="someone")

        assert calls, "the administrator's assignment did not go through"
        assert device_assign.get_mock_assignment(DEVICE_ID) == "t9"

    def test_no_session_assigns_nothing(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            device_assign.prototype_assignments,
            "assign_technician",
            lambda *a, **k: calls.append(a),
        )
        device_assign.clear_mock_assignments()

        self._call(None, technician="someone")

        assert calls == []
        assert device_assign.get_mock_assignment(DEVICE_ID) is None


# --------------------------------------------------------------------------
# The rule is not reimplemented here
# --------------------------------------------------------------------------


class TestCallbacksDoNotContainTheRule:
    @pytest.mark.parametrize(
        "module", [device_manage, device_assign], ids=["device_manage", "device_assign"]
    )
    def test_no_role_string_comparison_in_the_callback_module(self, module):
        """A role literal in a callback means the matrix was partly copied
        out of the policy table — the start of two answers to one question."""
        import pathlib
        import re

        source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        offenders = [
            line.strip()
            for line in source.splitlines()
            if re.search(r'==\s*["\'](administrator|technician|general)["\']', line)
            or re.search(r'["\'](administrator|technician|general)["\']\s*==', line)
        ]
        assert offenders == [], offenders


# --------------------------------------------------------------------------
# Device registration — the device-less guard
# --------------------------------------------------------------------------


class _RegisterSpy:
    """Stands in for the registration service and records whether it ran.

    The assertion here IS "was the mutation reached", so the boundary itself
    is what has to be observed. A denied role must not get this far.
    """

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return object()


def _silence_label_lookups(monkeypatch):
    """Stop the review-label reads from needing a database.

    Only used for the permitted case. A refused caller must not reach these
    at all, which is what leaving them un-patched proves.
    """
    monkeypatch.setattr(hierarchy_service, "list_plants", lambda **kw: [])
    monkeypatch.setattr(hierarchy_service, "list_transformers", lambda *a, **kw: [])


class TestDeviceRegistration:
    """The submit callback authorizes before it writes.

    ROUTE_POLICY already gates the page administrator-only, but the callback
    answers whoever invokes it and the session travels in a browser-side
    store. These tests call the handler directly — the path a caller
    bypassing the router takes — which is the only way this refusal is
    observable at all.
    """

    def _call(self, session):
        handler = _handlers(device_register)["_submit_registration"]
        return handler(1, "dv1", "plant-01", "plant-01-t1", "active", session)

    def test_administrator_reaches_the_registration_service(self, monkeypatch):
        spy = _RegisterSpy()
        _silence_label_lookups(monkeypatch)
        monkeypatch.setattr(device_register, "register_device", spy)

        self._call(ADMINISTRATOR_SESSION)

        assert spy.calls, "an administrator must reach register_device"

    @pytest.mark.parametrize(
        "session",
        [TECHNICIAN_SESSION, GENERAL_SESSION, STALE_SESSION, None],
        ids=["technician", "general", "stale", "no-session"],
    )
    def test_denied_callers_never_reach_the_database(self, monkeypatch, session):
        """No write, and no read either — the guard runs before the label
        lookups, so a refused caller touches the database not at all.

        The label lookups are deliberately NOT patched here: if the guard were
        placed after them this test would fail in the no-database suite.
        """
        spy = _RegisterSpy()
        monkeypatch.setattr(device_register, "register_device", spy)

        result = self._call(session)

        assert spy.calls == [], "a refused caller must not reach register_device"
        assert result[4] == {"display": "block"}, "the error slot must be shown"
        assert _is_refusal(result[5]), "the shared refusal notice must be rendered"

    def test_refusal_does_not_reveal_the_policy(self, monkeypatch):
        """The notice names no role, action or device."""
        monkeypatch.setattr(device_register, "register_device", _RegisterSpy())

        result = self._call(TECHNICIAN_SESSION)

        rendered = _rendered_text(result[5]).lower()
        for leak in ("technician", "register_device", "administrator"):
            assert leak not in rendered
